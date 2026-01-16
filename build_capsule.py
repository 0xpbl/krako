#!/usr/bin/env python3
"""
Build script to convert the Krako project into a Gemini capsule.
Converts .txt and .md files to Gemtext (.gmi) format.
"""

import os
import json
import re
from pathlib import Path
from typing import List, Tuple

# Directories
SOURCE_DIR = Path("dir/files")
CAPSULE_DIR = Path("capsule")
PAGES_DIR = CAPSULE_DIR / "pages"
COLLECTIONS_DIR = CAPSULE_DIR / "collections"

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
        # Collection has sections (like cartas/random/)
        for section_dir in collection_dir.iterdir():
            if section_dir.is_dir() and section_dir.name != 'sections.json':
                section = section_dir.name
                # Get all files (with or without extensions)
                for file_path in section_dir.iterdir():
                    if file_path.is_file() and file_path.name != 'sections.json':
                        files.append((section, file_path))
    else:
        # Collection has files directly (like mentalhealth/)
        # Put them in a "main" section
        for file_path in collection_dir.iterdir():
            if file_path.is_file() and file_path.name != 'sections.json':
                files.append(('main', file_path))
    
    return sorted(files, key=lambda x: x[1].name)

def get_footer() -> str:
    """Generate footer text."""
    return "\n---\n\ndesenvolvido por pablo murad - 2024 - 2026\n"

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
        
        # Output path
        section_dir = COLLECTIONS_DIR / collection_name / section
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
        
        section_index_path = COLLECTIONS_DIR / collection_name / section / "index.gmi"
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
        for file_path in files_by_section.get(section, []):
            if file_path.suffix:
                sanitized_name = sanitize_filename(file_path.stem)
            else:
                sanitized_name = sanitize_filename(file_path.name)
            all_files_flat.append((section, sanitized_name))
    
    for idx, (section, file_name) in enumerate(all_files_flat):
        file_path = COLLECTIONS_DIR / collection_name / section / f"{file_name}.gmi"
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add navigation at the beginning
            nav_lines = []
            nav_lines.append("")
            
            if idx > 0:
                prev_section, prev_name = all_files_flat[idx - 1]
                prev_display = prev_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/{collection_name}/{prev_section}/{prev_name}.gmi ← {prev_display}")
            
            nav_lines.append(f"=> /collections/{collection_name}/{section}/index.gmi ↑ Section index")
            
            if idx < len(all_files_flat) - 1:
                next_section, next_name = all_files_flat[idx + 1]
                next_display = next_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/{collection_name}/{next_section}/{next_name}.gmi {next_display} →")
            
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
            
            # If no heading found, add at the beginning
            if not first_heading_found:
                new_lines = nav_lines + new_lines
            
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
    """Translate collection name if needed (for Portuguese to English)."""
    if sections_data:
        main_menu_name = sections_data.get('mainMenuName', name.title())
        if main_menu_name == 'Cartas para Pablo':
            return 'Letters for Pablo'
        elif main_menu_name == 'Cartas':
            return 'Letters'
        return main_menu_name
    
    # Handle common compound words first (before any transformation)
    common_words = {
        'mentalhealth': 'Mental Health',
        'mental health': 'Mental Health',
    }
    
    name_lower = name.lower().replace('_', ' ')
    if name_lower in common_words:
        return common_words[name_lower]
    
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # Add spaces before capital letters (for camelCase)
    name = re.sub(r'(?<!^)(?<! )([A-Z])', r' \1', name)
    
    return name.title()

def build_index(pages: List[str], collections_data: dict):
    """
    Generate index.gmi (home page).
    collections_data: dict mapping collection_name -> sections_data
    """
    content = """```
 __                   __          
│  │ ______________  │  │ ______  
│  │╱ ╱╲_  __ ╲__  ╲ │  │╱ ╱  _ ╲ 
│    <  │  │ ╲╱╱ __ ╲│    <  <_> )
│__│_ ╲ │__│  (____  ╱__│_ ╲____╱ 
     ╲╱            ╲╱     ╲╱      
```

# Krako

the Quantum Experimental Laboratories at 0xpblab — directory

A web1-style directory of interesting places on the internet.

This is a Gemini capsule.

---

## Welcome

Welcome to a mildly organized pile of internet oddities, lovingly indexed by 0xpblab.

Here you'll find a collection of things that made someone go "hmm", things that made someone go "why", and things that made someone go "what".

The internet is weird, and that's okay.

---

## Explore

"""
    
    # Count pages (excluding empty index)
    page_count = len([p for p in pages if p != "index"])
    
    if pages:
        content += "### Pages\n\n"
        for page in pages:
            if page == "index":
                continue  # Skip empty index page
            # Keep original case if it's already uppercase/mixed, otherwise use uppercase
            page_display = page.replace('_', ' ')
            # If it contains numbers or is already in a special format, preserve it
            if page.lower() == 'recomendati0n':
                page_display = 'Recomendati0N'
            else:
                page_display = page_display.upper()
            content += f"=> /pages/{page}.gmi {page_display}\n"
        content += "\n"
    
    if collections_data:
        content += "### Collections\n\n"
        for collection_name in sorted(collections_data.keys()):
            sections_data = collections_data[collection_name]
            if sections_data:
                collection_display = translate_collection_name(collection_name, sections_data)
                # Convert to uppercase for display
                collection_display = collection_display.upper()
                # If collection has only one section, link directly to section index
                sections_order = sections_data.get('order', [])
                if len(sections_order) == 1:
                    # Single section - link directly to section index
                    section = sections_order[0]
                    content += f"=> /collections/{collection_name}/{section}/index.gmi {collection_display}\n"
                else:
                    # Multiple sections - link to collection index
                    content += f"=> /collections/{collection_name}/index.gmi {collection_display}\n"
            else:
                collection_display = translate_collection_name(collection_name)
                collection_display = collection_display.upper()
                content += f"=> /collections/{collection_name}/index.gmi {collection_display}\n"
        content += "\n"
    
    content += """---

## Quick Start

"""
    
    if page_count > 0:
        if page_count == 1:
            content += "=> /pages/recomendati0n.gmi Browse curated links\n"
        else:
            content += f"=> /pages/recomendati0n.gmi Browse {page_count} curated links\n"
    
    if collections_data:
        for collection_name in sorted(collections_data.keys()):
            sections_data = collections_data[collection_name]
            if sections_data:
                collection_display = translate_collection_name(collection_name, sections_data)
                # If collection has only one section, link directly to section index
                sections_order = sections_data.get('order', [])
                if len(sections_order) == 1:
                    section = sections_order[0]
                    link_path = f"/collections/{collection_name}/{section}/index.gmi"
                else:
                    link_path = f"/collections/{collection_name}/index.gmi"
                
                # Add a generic description based on collection name
                if 'cartas' in collection_name.lower():
                    content += f"=> {link_path} Explore personal letters collection\n"
                elif 'mental' in collection_name.lower():
                    content += f"=> {link_path} Explore {collection_display.lower()} collection\n"
                else:
                    content += f"=> {link_path} Explore {collection_display.lower()} collection\n"
    
    content += """
---

## About

This capsule is a curated collection of interesting places on the internet and personal correspondence from the early web era.

Navigate using the links above, or explore the collections to discover content that captures the spirit of the independent web.

Enjoy your journey through the weird and wonderful corners of the internet.

---

*Crafted with questionable taste and questionable methods*

"""
    
    write_gmi_file(CAPSULE_DIR / "index.gmi", content, add_footer=True)
    print(f"[OK] Generated index.gmi")

def main():
    """Main function."""
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
    
    # Build index
    print("Generating index.gmi...")
    build_index(pages, collections_data)
    print()
    
    print("Build complete!")
    print(f"Capsule generated at: {CAPSULE_DIR.absolute()}")

if __name__ == "__main__":
    main()
