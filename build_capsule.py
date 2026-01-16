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

def load_sections_json() -> dict:
    """Load sections.json from cartas collection."""
    sections_file = SOURCE_DIR / "cartas" / "sections.json"
    if sections_file.exists():
        with open(sections_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def write_gmi_file(path: Path, content: str):
    """Write .gmi file."""
    ensure_dir(path.parent)
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
        
        write_gmi_file(gmi_file, gmi_content)
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

def build_cartas_collection():
    """Process cartas collection and generate .gmi files."""
    sections_data = load_sections_json()
    if not sections_data:
        print("[WARNING] sections.json not found, skipping cartas collection")
        return None
    
    cartas_files = get_all_cartas_files()
    if not cartas_files:
        print("[WARNING] No carta files found")
        return None
    
    # Organize cartas by section
    cartas_by_section = {}
    for section, file_path in cartas_files:
        if section not in cartas_by_section:
            cartas_by_section[section] = []
        cartas_by_section[section].append(file_path)
    
    # Sort cartas in each section
    for section in cartas_by_section:
        cartas_by_section[section].sort(key=lambda x: x.name)
    
    # Convert each carta
    carta_paths = []  # List of (section, filename) for navigation
    for section, file_path in cartas_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        gmi_content = convert_md_to_gmi(content)
        
        # Output path
        section_dir = COLLECTIONS_DIR / "cartas" / section
        gmi_file = section_dir / f"{file_path.stem}.gmi"
        
        write_gmi_file(gmi_file, gmi_content)
        carta_paths.append((section, file_path.stem))
        print(f"[OK] Converted carta: {section}/{file_path.name} -> {gmi_file}")
    
    # Generate collection index
    collection_index_path = COLLECTIONS_DIR / "cartas" / "index.gmi"
    # Translate mainMenuName if it's in Portuguese
    main_menu_name = sections_data.get('mainMenuName', 'Letters')
    if main_menu_name == 'Cartas para Pablo':
        main_menu_name = 'Letters for Pablo'
    elif main_menu_name == 'Cartas':
        main_menu_name = 'Letters'
    collection_index = f"# {main_menu_name}\n\n"
    
    sections_order = sections_data.get('order', list(cartas_by_section.keys()))
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section)
        collection_index += f"## {section_name}\n\n"
        collection_index += f"=> /collections/cartas/{section}/index.gmi View {section_name}\n\n"
    
    write_gmi_file(collection_index_path, collection_index)
    print(f"[OK] Generated collection index: {collection_index_path}")
    
    # Generate section indices
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section)
        section_cartas = cartas_by_section.get(section, [])
        
        section_index_path = COLLECTIONS_DIR / "cartas" / section / "index.gmi"
        section_index = f"# {section_name}\n\n"
        section_index += f"=> /collections/cartas/index.gmi ← Back to collection\n\n"
        section_index += "## Letters\n\n"
        
        for carta_file in section_cartas:
            carta_name = carta_file.stem.replace('_', ' ').title()
            section_index += f"=> /collections/cartas/{section}/{carta_file.stem}.gmi {carta_name}\n"
        
        write_gmi_file(section_index_path, section_index)
        print(f"[OK] Generated section index: {section_index_path}")
    
    # Add previous/next navigation to cartas
    all_cartas_flat = []
    for section in sections_order:
        for carta_file in cartas_by_section.get(section, []):
            all_cartas_flat.append((section, carta_file.stem))
    
    for idx, (section, carta_name) in enumerate(all_cartas_flat):
        carta_path = COLLECTIONS_DIR / "cartas" / section / f"{carta_name}.gmi"
        
        if carta_path.exists():
            with open(carta_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add navigation at the beginning
            nav_lines = []
            nav_lines.append("")
            
            if idx > 0:
                prev_section, prev_name = all_cartas_flat[idx - 1]
                prev_display = prev_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/cartas/{prev_section}/{prev_name}.gmi ← {prev_display}")
            
            nav_lines.append(f"=> /collections/cartas/{section}/index.gmi ↑ Section index")
            
            if idx < len(all_cartas_flat) - 1:
                next_section, next_name = all_cartas_flat[idx + 1]
                next_display = next_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/cartas/{next_section}/{next_name}.gmi {next_display} →")
            
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
            write_gmi_file(carta_path, updated_content)
    
    return sections_data

def build_index(pages: List[str], has_cartas: bool, cartas_name: str = None):
    """Generate index.gmi (home page)."""
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
            page_display = page.replace('_', ' ').title()
            content += f"=> /pages/{page}.gmi {page_display}\n"
        content += "\n"
    
    if has_cartas:
        content += "### Collections\n\n"
        if cartas_name:
            content += f"=> /collections/cartas/index.gmi {cartas_name}\n\n"
        else:
            # Load sections.json to get the translated name
            sections_data = load_sections_json()
            if sections_data:
                main_menu_name = sections_data.get('mainMenuName', 'Letters')
                if main_menu_name == 'Cartas para Pablo':
                    main_menu_name = 'Letters for Pablo'
                elif main_menu_name == 'Cartas':
                    main_menu_name = 'Letters'
                content += f"=> /collections/cartas/index.gmi {main_menu_name}\n\n"
            else:
                content += "=> /collections/cartas/index.gmi Letters\n\n"
    
    content += """---

## Quick Start

"""
    
    if page_count > 0:
        if page_count == 1:
            content += "=> /pages/recomendati0n.gmi Browse curated links\n"
        else:
            content += f"=> /pages/recomendati0n.gmi Browse {page_count} curated links\n"
    
    if has_cartas:
        content += "=> /collections/cartas/index.gmi Explore personal letters collection\n"
    
    content += """
---

## About

This capsule is a curated collection of interesting places on the internet and personal correspondence from the early web era.

Navigate using the links above, or explore the collections to discover content that captures the spirit of the independent web.

Enjoy your journey through the weird and wonderful corners of the internet.

---

*Crafted with questionable taste and questionable methods*

"""
    
    write_gmi_file(CAPSULE_DIR / "index.gmi", content)
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
    
    # Build cartas collection
    print("Processing cartas collection...")
    cartas_data = build_cartas_collection()
    print()
    
    # Build index
    print("Generating index.gmi...")
    # Get translated cartas name if collection exists
    cartas_name = None
    if cartas_data:
        main_menu_name = cartas_data.get('mainMenuName', 'Letters')
        if main_menu_name == 'Cartas para Pablo':
            cartas_name = 'Letters for Pablo'
        elif main_menu_name == 'Cartas':
            cartas_name = 'Letters'
        else:
            cartas_name = main_menu_name
    build_index(pages, cartas_data is not None, cartas_name)
    print()
    
    print("Build complete!")
    print(f"Capsule generated at: {CAPSULE_DIR.absolute()}")

if __name__ == "__main__":
    main()
