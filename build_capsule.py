#!/usr/bin/env python3
"""
Build script to convert the Krako project into a Gemini capsule.
Converts .txt and .md files to Gemtext (.gmi) format.
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Paths relative to script location (run from any cwd)
PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_ROOT / "dir" / "files"
CAPSULE_DIR = PROJECT_ROOT / "capsule"
PAGES_DIR = CAPSULE_DIR / "pages"
COLLECTIONS_DIR = CAPSULE_DIR / "collections"

# Home: Start here (5 curated links)
START_HERE_LINKS = [
    ("/collections/cartas/random/index.gmi", "Letters"),
    ("/collections/TEXTS/adventure/index.gmi", "TEXTS"),
    ("/pages/recomendati0n.gmi", "Curated links"),
    ("/pages/about.gmi", "About"),
    ("/pages/map.gmi", "Map"),
]
# Home: Best texts (up to ~10 anchor links; paths relative to capsule root)
BEST_TEXTS_LINKS = [
    ("/pages/recomendati0n.gmi", "Curated links"),
    ("/collections/cartas/random/index.gmi", "Letters"),
    ("/collections/TEXTS/adventure/index.gmi", "TEXTS"),
    ("/collections/TEXTS/100/index.gmi", "BBS 100"),
    ("/pages/about.gmi", "About"),
    ("/pages/now.gmi", "Now"),
    ("/pages/uses.gmi", "Uses"),
    ("/pages/colophon.gmi", "Colophon"),
]
# Trail ids used in home (pages: /pages/trail_<id>.gmi)
TRAIL_IDS = ["5min", "strange_texts", "personal_letters", "mental_health", "obscure_files"]
TRAIL_TITLES = {
    "5min": "Read in 5 minutes",
    "strange_texts": "Strange texts",
    "personal_letters": "Personal letters",
    "mental_health": "Mental health",
    "obscure_files": "Obscure files (TEXTS)",
}

# Deploy target: override with env KRAKO_DEPLOY_TARGET.
# Default is local path (script usually runs on the server). Use user@host:path for remote deploy.
DEPLOY_TARGET = os.environ.get("KRAKO_DEPLOY_TARGET", "/var/lib/krako/content")
DEPLOY_REMOTE_PATH = "/var/lib/krako/content"
DEPLOY_CHOWN = "krako:krako"

def ensure_dir(path: Path):
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)

def detect_file_format(content: str) -> str:
    """
    Detect if content is Markdown or plain text.
    Returns 'md' if Markdown syntax is detected, 'txt' otherwise.
    """
    # Check for Markdown indicators
    has_markdown_links = bool(re.search(r'\[([^\]]+)\]\(([^)]+)\)', content))
    has_markdown_headings = bool(re.search(r'^#{1,6}\s+', content, re.MULTILINE))
    has_markdown_bold = bool(re.search(r'\*\*[^*]+\*\*', content))
    has_markdown_code_blocks = bool(re.search(r'```', content))
    
    # If any Markdown syntax is found, treat as Markdown
    if has_markdown_links or has_markdown_headings or has_markdown_bold or has_markdown_code_blocks:
        return 'md'
    
    return 'txt'

def sanitize_filename(name: str) -> str:
    """
    Sanitize filename for URL-safe use.
    Replaces spaces with underscores and removes special characters.
    """
    # Replace spaces with underscores
    name = name.replace(' ', '_')
    # Remove or replace problematic characters
    name = re.sub(r'[^\w\-_\.]', '', name)
    return name

def convert_txt_to_gmi(content: str) -> str:
    """
    Convert .txt content to Gemtext.
    
    Rules:
    - Lines starting with '# ' → heading
    - Lines starting with '- https://...' → '=> https://...'
    - Empty lines preserved
    - Normal text preserved
    """
    lines = content.split('\n')
    result = []
    
    for line in lines:
        stripped = line.strip()
        
        # Heading
        if stripped.startswith('# '):
            result.append(stripped)
        # URL with '- ' prefix
        elif stripped.startswith('- ') and (stripped.startswith('- http://') or stripped.startswith('- https://')):
            url = stripped[2:].strip()
            result.append(f"=> {url}")
        # Empty line
        elif not stripped:
            result.append('')
        # Normal text
        else:
            result.append(line)
    
    return '\n'.join(result)

def convert_md_to_gmi(content: str) -> str:
    """
    Convert Markdown content to Gemtext.
    
    Rules:
    - Headings preserved (#, ##, ###)
    - Lists '- item' → '* item'
    - Links '[text](url)' → '=> url text'
    - Remove bold **text** → text
    - Remove italic *text* → text (but preserve lists)
    - Preserve code blocks
    """
    lines = content.split('\n')
    result = []
    in_code_block = False
    
    for line in lines:
        # Detect code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue
        
        if in_code_block:
            result.append(line)
            continue
        
        stripped = line.strip()
        
        # Headings (preserve)
        if re.match(r'^#{1,3}\s+', stripped):
            result.append(stripped)
        # Lists: '- item' → '* item'
        elif re.match(r'^-\s+', stripped):
            item = re.sub(r'^-\s+', '* ', stripped)
            # Remove inline formatting from list
            item = re.sub(r'\*\*(.+?)\*\*', r'\1', item)
            item = re.sub(r'\*(.+?)\*', r'\1', item)
            result.append(item)
        # Links: [text](url) → => url text
        elif '](' in line:
            # Process multiple links on the same line
            def replace_link(match):
                text = match.group(1)
                url = match.group(2)
                return f"=> {url} {text}"
            line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, line)
            # Remove remaining formatting
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            line = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\1', line)  # Italic, but not lists
            result.append(line)
        # Empty line
        elif not stripped:
            result.append('')
        # Normal text - remove inline formatting
        else:
            # Remove bold
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            # Remove italic (but not lists that were already processed)
            line = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\1', line)
            # Remove markdown horizontal rules (---)
            if stripped == '---':
                result.append('')
            else:
                result.append(line)
    
    return '\n'.join(result)

def discover_collections() -> List[str]:
    """
    Discover all collection directories in dir/files/.
    A collection is a directory that is not a .txt file.
    """
    collections = []
    if not SOURCE_DIR.exists():
        return collections
    
    for item in SOURCE_DIR.iterdir():
        if item.is_dir():
            # Check if it's not empty and has files (not just sections.json)
            has_files = False
            for subitem in item.iterdir():
                if subitem.is_file() and subitem.name != 'sections.json':
                    has_files = True
                    break
                elif subitem.is_dir():
                    # Check if subdirectory has files
                    for subfile in subitem.iterdir():
                        if subfile.is_file():
                            has_files = True
                            break
                    if has_files:
                        break
            
            if has_files:
                collections.append(item.name)
    
    return sorted(collections)

def get_all_txt_files() -> List[Path]:
    """Return list of .txt files in dir/files/."""
    txt_files = []
    if SOURCE_DIR.exists():
        for file in SOURCE_DIR.glob("*.txt"):
            if file.name != "index.txt":  # Exclude empty index.txt
                txt_files.append(file)
    return sorted(txt_files)

def get_all_cartas_files() -> List[Tuple[str, Path]]:
    """
    Return list of tuples (section, file_path) for .md files in cartas/.
    """
    cartas = []
    cartas_dir = SOURCE_DIR / "cartas"
    
    if cartas_dir.exists():
        for section_dir in cartas_dir.iterdir():
            if section_dir.is_dir():
                section = section_dir.name
                for md_file in section_dir.glob("*.md"):
                    cartas.append((section, md_file))
    
    return sorted(cartas, key=lambda x: x[1].name)

def load_sections_json(collection_name: str) -> dict:
    """Load sections.json from a collection directory."""
    sections_file = SOURCE_DIR / collection_name / "sections.json"
    if sections_file.exists():
        with open(sections_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def get_default_sections(collection_name: str, files_by_section: dict) -> dict:
    """Generate default sections.json structure if it doesn't exist."""
    # Use collection name as main menu name (with proper formatting)
    # Handle common compound words
    common_words = {
        'mentalhealth': 'Mental Health',
        'mental health': 'Mental Health',
    }
    
    name_lower = collection_name.lower().replace('_', ' ')
    if name_lower in common_words:
        main_menu_name = common_words[name_lower]
    else:
        # Replace underscores with spaces and title case
        main_menu_name = collection_name.replace('_', ' ').title()
    
    # If there's only one section, use it; otherwise use "main"
    sections = {}
    if len(files_by_section) == 1:
        section_key = list(files_by_section.keys())[0]
        sections[section_key] = section_key.replace('_', ' ').title()
    else:
        sections['main'] = 'Main'
    
    return {
        'mainMenuName': main_menu_name,
        'sections': sections,
        'order': list(files_by_section.keys())
    }

def get_collection_files(collection_name: str) -> List[Tuple[str, Path]]:
    """
    Return list of tuples (section, file_path) for files in a collection.
    Handles files with or without extensions.
    """
    collection_dir = SOURCE_DIR / collection_name
    files = []
    
    if not collection_dir.exists():
        return files
    
    # Check if collection has subdirectories (sections) or files directly
    has_sections = False
    for item in collection_dir.iterdir():
        if item.is_dir() and item.name != 'sections.json':
            has_sections = True
            break
    
    if has_sections:
        # Collection has sections (e.g. adventure/, 100/, or nested computers/CYBERSPACE/)
        for section_dir in sorted(collection_dir.iterdir()):
            if not section_dir.is_dir() or section_dir.name == 'sections.json':
                continue
            section_name = section_dir.name
            direct_files = [p for p in section_dir.iterdir() if p.is_file() and p.name != 'sections.json']
            subdirs = [p for p in section_dir.iterdir() if p.is_dir()]
            if direct_files:
                for file_path in direct_files:
                    files.append((section_name, file_path))
            elif subdirs:
                # Nested section (e.g. computers/ with CYBERSPACE, ASTRESEARCH)
                for subdir in sorted(subdirs):
                    subsection = f"{section_name}/{subdir.name}"
                    for file_path in subdir.iterdir():
                        if file_path.is_file() and file_path.name != 'sections.json':
                            files.append((subsection, file_path))
    else:
        # Collection has files directly (like mentalhealth/)
        # Put them in a "main" section
        for file_path in collection_dir.iterdir():
            if file_path.is_file() and file_path.name != 'sections.json':
                files.append(('main', file_path))
    
    return sorted(files, key=lambda x: x[1].name)

def get_footer() -> str:
    """Generate footer text."""
    return "\n---\n\nBy Pablo Murad — 2024–2026\n"

def write_gmi_file(path: Path, content: str, add_footer: bool = False):
    """Write .gmi file."""
    ensure_dir(path.parent)
    if add_footer:
        content = content.rstrip() + get_footer()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def build_pages():
    """Convert .txt files to .gmi pages."""
    txt_files = get_all_txt_files()
    page_names = []
    
    for txt_file in txt_files:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Skip empty files
        if not content:
            continue
        
        gmi_content = convert_txt_to_gmi(content)
        
        # File name without extension
        page_name = txt_file.stem
        gmi_file = PAGES_DIR / f"{page_name}.gmi"
        
        write_gmi_file(gmi_file, gmi_content, add_footer=True)
        page_names.append(page_name)
        print(f"[OK] Converted: {txt_file.name} -> {gmi_file}")
    
    # Remove empty index.gmi if it exists
    index_gmi = PAGES_DIR / "index.gmi"
    if index_gmi.exists():
        try:
            index_gmi.unlink()
            print(f"[OK] Removed empty: {index_gmi}")
        except Exception:
            pass
    
    return page_names

def build_collection(collection_name: str):
    """Process any collection and generate .gmi files."""
    collection_files = get_collection_files(collection_name)
    if not collection_files:
        print(f"[WARNING] No files found in collection: {collection_name}")
        return None
    
    # Organize files by section
    files_by_section = {}
    for section, file_path in collection_files:
        if section not in files_by_section:
            files_by_section[section] = []
        files_by_section[section].append(file_path)
    
    # Sort files in each section
    for section in files_by_section:
        files_by_section[section].sort(key=lambda x: x.name)
    
    # Load or create sections.json
    sections_data = load_sections_json(collection_name)
    if not sections_data:
        sections_data = get_default_sections(collection_name, files_by_section)
        print(f"[INFO] Using default sections for {collection_name}")
    
    # Convert each file
    file_paths = []  # List of (section, sanitized_filename) for navigation
    for section, file_path in collection_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Detect format and convert
        file_format = detect_file_format(content)
        if file_format == 'md':
            gmi_content = convert_md_to_gmi(content)
        else:
            gmi_content = convert_txt_to_gmi(content)
        
        # Sanitize filename for output
        if file_path.suffix:
            # Has extension, use stem
            sanitized_name = sanitize_filename(file_path.stem)
        else:
            # No extension, sanitize the whole name
            sanitized_name = sanitize_filename(file_path.name)
        
        # Output path (section may be nested, e.g. "computers/CYBERSPACE")
        section_dir = COLLECTIONS_DIR / collection_name / Path(section)
        gmi_file = section_dir / f"{sanitized_name}.gmi"
        
        write_gmi_file(gmi_file, gmi_content, add_footer=True)
        file_paths.append((section, sanitized_name))
        print(f"[OK] Converted {collection_name}: {section}/{file_path.name} -> {gmi_file}")
    
    # Generate collection index
    collection_index_path = COLLECTIONS_DIR / collection_name / "index.gmi"
    # Translate mainMenuName if it's in Portuguese (for cartas compatibility)
    main_menu_name = sections_data.get('mainMenuName', collection_name.title())
    if main_menu_name == 'Cartas para Pablo':
        main_menu_name = 'Letters for Pablo'
    elif main_menu_name == 'Cartas':
        main_menu_name = 'Letters'
    collection_index = f"# {main_menu_name}\n\n"
    intro = sections_data.get('intro')
    if intro:
        collection_index += intro.strip() + "\n\n"
    sections_order = sections_data.get('order', list(files_by_section.keys()))
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section.replace('_', ' ').title())
        collection_index += f"## {section_name}\n\n"
        collection_index += f"=> /collections/{collection_name}/{section}/index.gmi View {section_name}\n\n"
    
    write_gmi_file(collection_index_path, collection_index, add_footer=True)
    print(f"[OK] Generated collection index: {collection_index_path}")
    
    # Generate section indices
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section.replace('_', ' ').title())
        section_files = files_by_section.get(section, [])
        
        section_index_path = COLLECTIONS_DIR / collection_name / Path(section) / "index.gmi"
        section_index = f"# {section_name}\n\n"
        section_index += f"=> /collections/{collection_name}/index.gmi ← Back to collection\n\n"
        section_index += "## Documents\n\n"
        
        for file_path in section_files:
            if file_path.suffix:
                display_name = file_path.stem.replace('_', ' ').title()
                sanitized_name = sanitize_filename(file_path.stem)
            else:
                display_name = file_path.name.replace('_', ' ').title()
                sanitized_name = sanitize_filename(file_path.name)
            section_index += f"=> /collections/{collection_name}/{section}/{sanitized_name}.gmi {display_name}\n"
        
        write_gmi_file(section_index_path, section_index, add_footer=True)
        print(f"[OK] Generated section index: {section_index_path}")
    
    # Add previous/next navigation to files
    all_files_flat = []
    for section in sections_order:
        for src_path in files_by_section.get(section, []):
            if src_path.suffix:
                sanitized_name = sanitize_filename(src_path.stem)
            else:
                sanitized_name = sanitize_filename(src_path.name)
            all_files_flat.append((section, sanitized_name, src_path))
    
    for idx, (section, file_name, src_path) in enumerate(all_files_flat):
        file_path = COLLECTIONS_DIR / collection_name / Path(section) / f"{file_name}.gmi"
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add navigation at the beginning
            nav_lines = []
            nav_lines.append("")
            # Date line for dated documents (e.g. letters YYYY-MM-DD_title)
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", src_path.stem if src_path.suffix else src_path.name)
            if date_match:
                nav_lines.append("Date: " + date_match.group(1))
                nav_lines.append("")
            
            if idx > 0:
                prev_section, prev_name, _ = all_files_flat[idx - 1]
                prev_display = prev_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/{collection_name}/{prev_section}/{prev_name}.gmi ← {prev_display}")
            
            nav_lines.append(f"=> /collections/{collection_name}/{section}/index.gmi ↑ Section index")
            
            if idx < len(all_files_flat) - 1:
                next_section, next_name, _ = all_files_flat[idx + 1]
                next_display = next_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/{collection_name}/{next_section}/{next_name}.gmi {next_display} →")
                nav_lines.append("Read this next:")
                nav_lines.append(f"=> /collections/{collection_name}/{next_section}/{next_name}.gmi {next_display}")

            nav_lines.append("")
            nav_lines.append("---")
            nav_lines.append("")
            
            # Insert navigation after first heading
            lines = content.split('\n')
            new_lines = []
            first_heading_found = False
            
            for line in lines:
                if not first_heading_found and line.strip().startswith('#'):
                    first_heading_found = True
                    new_lines.append(line)
                    new_lines.extend(nav_lines)
                else:
                    new_lines.append(line)
            
            # If no heading found, add title from filename and nav at the beginning
            if not first_heading_found:
                title = file_name.replace("_", " ").title()
                new_lines = ["# " + title, ""] + nav_lines + new_lines
            
            updated_content = '\n'.join(new_lines)
            # Keep footer if it exists, otherwise add it
            if get_footer().strip() not in updated_content:
                write_gmi_file(file_path, updated_content, add_footer=True)
            else:
                write_gmi_file(file_path, updated_content, add_footer=False)
    
    return sections_data

def build_cartas_collection():
    """Process cartas collection and generate .gmi files."""
    return build_collection("cartas")

def translate_collection_name(name: str, sections_data: dict = None) -> str:
    """Translate collection name if needed (for Portuguese to English). Menu uses mainMenuName from sections.json (e.g. TEXTS)."""
    if sections_data:
        main_menu_name = sections_data.get('mainMenuName', name.title())
        if main_menu_name == 'Cartas para Pablo':
            return 'Letters for Pablo'
        elif main_menu_name == 'Cartas':
            return 'Letters'
        return main_menu_name

    # Handle common compound words when no sections_data
    common_words = {
        'mentalhealth': 'Mental Health',
        'mental health': 'Mental Health',
        'texts': 'TEXTS',
    }
    name_lower = name.lower().replace('_', ' ')
    if name_lower in common_words:
        return common_words[name_lower]

    name = name.replace('_', ' ')
    name = re.sub(r'(?<!^)(?<! )([A-Z])', r' \1', name)
    return name.title()

def build_index(pages: List[str], collections_data: dict):
    """
    Generate index.gmi (home page) in English.
    Branding: The Great Capsule of Pablo Murad.
    Structure: Start here, Best texts, What's new, Trails; footer links to about/now/uses/colophon/changelog/map.
    """
    content = "# The Great Capsule of Pablo Murad\n\n"
    content += "A personal space for exploration, reading trails, and archived texts.\n\n"
    content += "---\n\n"

    content += "## Start here\n\n"
    for path, label in START_HERE_LINKS:
        content += f"=> {path} {label}\n"
    content += "\n"

    content += "## Best texts\n\n"
    for path, label in BEST_TEXTS_LINKS:
        content += f"=> {path} {label}\n"
    content += "\n"

    content += "## What's new\n\n"
    content += "=> /pages/changelog.gmi Changelog\n\n"

    content += "## Trails\n\n"
    for tid in TRAIL_IDS:
        title = TRAIL_TITLES.get(tid, tid.replace("_", " ").title())
        content += f"=> /pages/trail_{tid}.gmi {title}\n"
    content += "\n"

    content += "---\n\n"
    content += "=> /pages/about.gmi About\n"
    content += "=> /pages/now.gmi Now\n"
    content += "=> /pages/uses.gmi Uses\n"
    content += "=> /pages/colophon.gmi Colophon\n"
    content += "=> /pages/changelog.gmi Changelog\n"
    content += "=> /pages/map.gmi Map\n"

    write_gmi_file(CAPSULE_DIR / "index.gmi", content, add_footer=True)
    print(f"[OK] Generated index.gmi")

def build_trails():
    """Load trails.json and generate /pages/trail_<id>.gmi for each trail."""
    trails_file = SOURCE_DIR / "trails.json"
    if not trails_file.exists():
        print("[WARNING] trails.json not found; skipping trail pages.")
        return
    with open(trails_file, "r", encoding="utf-8") as f:
        trails = json.load(f)
    for t in trails:
        tid = t.get("id")
        title = t.get("title", tid.replace("_", " ").title())
        links = t.get("links", [])
        if not tid:
            continue
        content = f"# {title}\n\n"
        for item in links:
            if isinstance(item, list):
                path, label = item[0], item[1]
            else:
                path, label = item, item
            content += f"=> {path} {label}\n"
        out = PAGES_DIR / f"trail_{tid}.gmi"
        write_gmi_file(out, content, add_footer=True)
        print(f"[OK] Generated {out.name}")
    return len(trails)

def build_random():
    """Generate random.gmi: one random document link (picked at build time)."""
    doc_links = []
    for gmi in COLLECTIONS_DIR.rglob("*.gmi"):
        if gmi.name == "index.gmi":
            continue
        try:
            rel = gmi.relative_to(COLLECTIONS_DIR)
            path = "/collections/" + rel.as_posix()
            display = gmi.stem.replace("_", " ").title()
            doc_links.append((path, display))
        except ValueError:
            continue
    if not doc_links:
        content = "# Random\n\nNo documents in collections yet.\n"
    else:
        path, display = random.choice(doc_links)
        content = "# Random\n\n=> " + path + " " + display + "\n"
    write_gmi_file(PAGES_DIR / "random.gmi", content, add_footer=True)
    print("[OK] Generated random.gmi")

def build_by_year():
    """Generate by_year.gmi: letters grouped by year (from cartas filenames)."""
    cartas_dir = SOURCE_DIR / "cartas"
    by_year = {}
    year_re = re.compile(r"^(\d{4})-\d{2}-\d{2}")
    if cartas_dir.exists():
        for section_dir in cartas_dir.iterdir():
            if not section_dir.is_dir():
                continue
            for f in section_dir.iterdir():
                if not f.is_file() or f.suffix not in (".md", ".txt", ""):
                    continue
                name = f.stem if f.suffix else f.name
                m = year_re.match(name)
                if m:
                    year = m.group(1)
                    sanitized = sanitize_filename(name)
                    path = f"/collections/cartas/{section_dir.name}/{sanitized}.gmi"
                    by_year.setdefault(year, []).append((path, name.replace("_", " ").title()))
    for year in by_year:
        by_year[year].sort(key=lambda x: x[1])
    content = "# By year\n\nLetters grouped by year.\n\n---\n\n"
    for year in sorted(by_year.keys(), reverse=True):
        content += f"## {year}\n\n"
        for path, label in by_year[year]:
            content += f"=> {path} {label}\n"
        content += "\n"
    write_gmi_file(PAGES_DIR / "by_year.gmi", content, add_footer=True)
    print("[OK] Generated by_year.gmi")

def build_discovery_placeholders():
    """Generate placeholder pages for tags and mood (To be populated / Coming soon)."""
    mood_names = ["Light", "Weird", "Technical", "Intimate", "Dark"]
    content_tags = "# Tags\n\nComing soon.\n"
    write_gmi_file(PAGES_DIR / "tags.gmi", content_tags, add_footer=True)
    for mood in mood_names:
        slug = mood.lower()
        content = f"# {mood}\n\nTo be populated.\n"
        write_gmi_file(PAGES_DIR / f"mood_{slug}.gmi", content, add_footer=True)
    print("[OK] Generated tags.gmi and mood_*.gmi placeholders")

def build_map(pages: List[str], collections_data: dict):
    """Generate map.gmi: structured index of collections, sections, and static pages (English)."""
    content = "# Map\n\n"
    content += "Structured index of the capsule.\n\n"
    content += "---\n\n"

    content += "## Static pages\n\n"
    for page in sorted(pages):
        if page == "index":
            continue
        label = page.replace("_", " ").title()
        if page.lower() == "recomendati0n":
            label = "Recomendati0n"
        content += f"=> /pages/{page}.gmi {label}\n"
    content += "\n"

    content += "## Collections\n\n"
    for collection_name in sorted(collections_data.keys()):
        sections_data = collections_data[collection_name]
        display_name = translate_collection_name(collection_name, sections_data)
        content += f"### {display_name}\n\n"
        content += f"=> /collections/{collection_name}/index.gmi Collection index\n\n"
        sections_order = sections_data.get("order", [])
        sections_dict = sections_data.get("sections", {})
        for section in sections_order:
            section_display = sections_dict.get(section, section.replace("_", " ").title())
            content += f"=> /collections/{collection_name}/{section}/index.gmi {section_display}\n"
        content += "\n"

    write_gmi_file(PAGES_DIR / "map.gmi", content, add_footer=True)
    print(f"[OK] Generated map.gmi")

def run_deploy():
    """Sync capsule/ to DEPLOY_TARGET (local path or user@host:path). Creates target dir if needed; runs chown after."""
    capsule_src = CAPSULE_DIR.resolve()
    if not capsule_src.exists():
        print("Deploy failed: capsule directory not found.")
        sys.exit(1)
    src = str(capsule_src).rstrip(os.sep) + os.sep
    target = DEPLOY_TARGET
    print("Deploying capsule to", target, "...")
    # Remote = user@host:path (contains ":" and "@" before the colon); else local path
    is_local = not (":" in target and "@" in target.split(":")[0])

    try:
        if is_local:
            dest_path = target.rstrip(os.sep)
            os.makedirs(dest_path, exist_ok=True)
            r = subprocess.run(
                ["rsync", "-a", "--delete", src, dest_path + os.sep],
                check=False,
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                print("Deploy failed (rsync):", r.stderr or r.stdout or "unknown error")
                sys.exit(1)
            r2 = subprocess.run(
                ["chown", "-R", DEPLOY_CHOWN, dest_path],
                check=False,
                capture_output=True,
                text=True,
            )
            if r2.returncode != 0:
                print("Deploy (chown) failed:", r2.stderr or r2.stdout or "unknown error")
                sys.exit(1)
        else:
            host = target.split(":")[0]
            remote_path = target.split(":", 1)[1].rstrip("/")
            # Ensure remote directory exists so rsync receiver can write
            subprocess.run(
                ["ssh", host, f"mkdir -p {remote_path}"],
                check=False,
                capture_output=True,
                text=True,
            )
            r = subprocess.run(
                ["rsync", "-a", "--delete", src, target],
                check=False,
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                print("Deploy failed (rsync):", r.stderr or r.stdout or "unknown error")
                sys.exit(1)
            r2 = subprocess.run(
                ["ssh", host, f"chown -R {DEPLOY_CHOWN} {remote_path}"],
                check=False,
                capture_output=True,
                text=True,
            )
            if r2.returncode != 0:
                print("Deploy (chown) failed:", r2.stderr or r2.stdout or "unknown error")
                sys.exit(1)
        print("Deploy complete.")
    except FileNotFoundError as e:
        print("Deploy failed: rsync or ssh not found.", e)
        sys.exit(1)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Build Krako Gemini capsule.")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="After build, rsync capsule to server and run chown (see DEPLOY_TARGET).",
    )
    args = parser.parse_args()

    print("Starting Gemini capsule build...\n")

    # Create directories
    ensure_dir(CAPSULE_DIR)
    ensure_dir(PAGES_DIR)
    ensure_dir(COLLECTIONS_DIR)

    # Build pages
    print("Converting pages...")
    pages = build_pages()
    print()

    # Discover and build collections
    print("Discovering collections...")
    collections = discover_collections()
    print(f"Found collections: {', '.join(collections) if collections else 'none'}")
    print()

    collections_data = {}
    for collection_name in collections:
        print(f"Processing {collection_name} collection...")
        collection_data = build_collection(collection_name)
        if collection_data:
            collections_data[collection_name] = collection_data
        print()

    # Build trails (from trails.json)
    print("Generating trail pages...")
    build_trails()
    print()

    # Discovery: random, by_year, placeholders
    print("Generating discovery pages...")
    build_random()
    build_by_year()
    build_discovery_placeholders()
    print()

    # Build index
    print("Generating index.gmi...")
    build_index(pages, collections_data)
    print()

    # Build map
    print("Generating map.gmi...")
    build_map(pages, collections_data)
    print()

    print("Build complete!")
    print(f"Capsule generated at: {CAPSULE_DIR.absolute()}")

    if args.deploy:
        print()
        run_deploy()

if __name__ == "__main__":
    main()
