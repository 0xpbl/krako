#!/usr/bin/env python3
"""
Build script para converter o projeto Krako em uma capsule Gemini.
Converte arquivos .txt e .md para formato Gemtext (.gmi).
"""

import os
import json
import re
from pathlib import Path
from typing import List, Tuple

# Diretórios
SOURCE_DIR = Path("dir/files")
CAPSULE_DIR = Path("capsule")
PAGES_DIR = CAPSULE_DIR / "pages"
COLLECTIONS_DIR = CAPSULE_DIR / "collections"

def ensure_dir(path: Path):
    """Cria diretório se não existir."""
    path.mkdir(parents=True, exist_ok=True)

def convert_txt_to_gmi(content: str) -> str:
    """
    Converte conteúdo .txt para Gemtext.
    
    Regras:
    - Linhas começando com '# ' → heading
    - Linhas começando com '- https://...' → '=> https://...'
    - Linhas vazias preservadas
    - Texto normal preservado
    """
    lines = content.split('\n')
    result = []
    
    for line in lines:
        stripped = line.strip()
        
        # Heading
        if stripped.startswith('# '):
            result.append(stripped)
        # URL com prefixo '- '
        elif stripped.startswith('- ') and (stripped.startswith('- http://') or stripped.startswith('- https://')):
            url = stripped[2:].strip()
            result.append(f"=> {url}")
        # Linha vazia
        elif not stripped:
            result.append('')
        # Texto normal
        else:
            result.append(line)
    
    return '\n'.join(result)

def convert_md_to_gmi(content: str) -> str:
    """
    Converte conteúdo Markdown para Gemtext.
    
    Regras:
    - Headings preservados (#, ##, ###)
    - Listas '- item' → '* item'
    - Links '[texto](url)' → '=> url texto'
    - Remover negrito **texto** → texto
    - Remover itálico *texto* → texto (mas preservar listas)
    - Preservar blocos de código
    """
    lines = content.split('\n')
    result = []
    in_code_block = False
    
    for line in lines:
        # Detectar blocos de código
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            result.append(line)
            continue
        
        if in_code_block:
            result.append(line)
            continue
        
        stripped = line.strip()
        
        # Headings (preservar)
        if re.match(r'^#{1,3}\s+', stripped):
            result.append(stripped)
        # Listas: '- item' → '* item'
        elif re.match(r'^-\s+', stripped):
            item = re.sub(r'^-\s+', '* ', stripped)
            # Remover formatação inline da lista
            item = re.sub(r'\*\*(.+?)\*\*', r'\1', item)
            item = re.sub(r'\*(.+?)\*', r'\1', item)
            result.append(item)
        # Links: [texto](url) → => url texto
        elif '](' in line:
            # Processar múltiplos links na mesma linha
            def replace_link(match):
                text = match.group(1)
                url = match.group(2)
                return f"=> {url} {text}"
            line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, line)
            # Remover formatação restante
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            line = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\1', line)  # Itálico, mas não listas
            result.append(line)
        # Linha vazia
        elif not stripped:
            result.append('')
        # Texto normal - remover formatação inline
        else:
            # Remover negrito
            line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
            # Remover itálico (mas não listas que já foram processadas)
            line = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'\1', line)
            # Remover regras horizontais markdown (---)
            if stripped == '---':
                result.append('')
            else:
                result.append(line)
    
    return '\n'.join(result)

def get_all_txt_files() -> List[Path]:
    """Retorna lista de arquivos .txt em dir/files/."""
    txt_files = []
    if SOURCE_DIR.exists():
        for file in SOURCE_DIR.glob("*.txt"):
            if file.name != "index.txt" or file.name == "index.txt":  # Incluir todos
                txt_files.append(file)
    return sorted(txt_files)

def get_all_cartas_files() -> List[Tuple[str, Path]]:
    """
    Retorna lista de tuplas (section, file_path) para arquivos .md em cartas/.
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
    """Carrega sections.json da coleção cartas."""
    sections_file = SOURCE_DIR / "cartas" / "sections.json"
    if sections_file.exists():
        with open(sections_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def write_gmi_file(path: Path, content: str):
    """Escreve arquivo .gmi."""
    ensure_dir(path.parent)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def build_pages():
    """Converte arquivos .txt para páginas .gmi."""
    txt_files = get_all_txt_files()
    page_names = []
    
    for txt_file in txt_files:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        gmi_content = convert_txt_to_gmi(content)
        
        # Nome do arquivo sem extensão
        page_name = txt_file.stem
        gmi_file = PAGES_DIR / f"{page_name}.gmi"
        
        write_gmi_file(gmi_file, gmi_content)
        page_names.append(page_name)
        print(f"[OK] Convertido: {txt_file.name} -> {gmi_file}")
    
    return page_names

def build_cartas_collection():
    """Processa coleção cartas e gera arquivos .gmi."""
    sections_data = load_sections_json()
    if not sections_data:
        print("[AVISO] sections.json nao encontrado, pulando colecao cartas")
        return None
    
    cartas_files = get_all_cartas_files()
    if not cartas_files:
        print("[AVISO] Nenhum arquivo de carta encontrado")
        return None
    
    # Organizar cartas por seção
    cartas_by_section = {}
    for section, file_path in cartas_files:
        if section not in cartas_by_section:
            cartas_by_section[section] = []
        cartas_by_section[section].append(file_path)
    
    # Ordenar cartas em cada seção
    for section in cartas_by_section:
        cartas_by_section[section].sort(key=lambda x: x.name)
    
    # Converter cada carta
    carta_paths = []  # Lista de (section, filename) para navegação
    for section, file_path in cartas_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        gmi_content = convert_md_to_gmi(content)
        
        # Caminho de saída
        section_dir = COLLECTIONS_DIR / "cartas" / section
        gmi_file = section_dir / f"{file_path.stem}.gmi"
        
        write_gmi_file(gmi_file, gmi_content)
        carta_paths.append((section, file_path.stem))
        print(f"[OK] Convertido carta: {section}/{file_path.name} -> {gmi_file}")
    
    # Gerar índice da coleção
    collection_index_path = COLLECTIONS_DIR / "cartas" / "index.gmi"
    collection_index = f"# {sections_data.get('mainMenuName', 'Cartas')}\n\n"
    
    sections_order = sections_data.get('order', list(cartas_by_section.keys()))
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section)
        collection_index += f"## {section_name}\n\n"
        collection_index += f"=> /collections/cartas/{section}/index.gmi Ver cartas de {section_name}\n\n"
    
    write_gmi_file(collection_index_path, collection_index)
    print(f"[OK] Gerado indice da colecao: {collection_index_path}")
    
    # Gerar índices por seção
    for section in sections_order:
        section_name = sections_data.get('sections', {}).get(section, section)
        section_cartas = cartas_by_section.get(section, [])
        
        section_index_path = COLLECTIONS_DIR / "cartas" / section / "index.gmi"
        section_index = f"# {section_name}\n\n"
        section_index += f"=> /collections/cartas/index.gmi ← Voltar para coleção\n\n"
        section_index += "## Cartas\n\n"
        
        for carta_file in section_cartas:
            carta_name = carta_file.stem.replace('_', ' ').title()
            section_index += f"=> /collections/cartas/{section}/{carta_file.stem}.gmi {carta_name}\n"
        
        write_gmi_file(section_index_path, section_index)
        print(f"[OK] Gerado indice da secao: {section_index_path}")
    
    # Adicionar navegação anterior/próxima nas cartas
    all_cartas_flat = []
    for section in sections_order:
        for carta_file in cartas_by_section.get(section, []):
            all_cartas_flat.append((section, carta_file.stem))
    
    for idx, (section, carta_name) in enumerate(all_cartas_flat):
        carta_path = COLLECTIONS_DIR / "cartas" / section / f"{carta_name}.gmi"
        
        if carta_path.exists():
            with open(carta_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Adicionar navegação no início
            nav_lines = []
            nav_lines.append("")
            
            if idx > 0:
                prev_section, prev_name = all_cartas_flat[idx - 1]
                prev_display = prev_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/cartas/{prev_section}/{prev_name}.gmi ← {prev_display}")
            
            nav_lines.append(f"=> /collections/cartas/{section}/index.gmi ↑ Índice da seção")
            
            if idx < len(all_cartas_flat) - 1:
                next_section, next_name = all_cartas_flat[idx + 1]
                next_display = next_name.replace('_', ' ').title()
                nav_lines.append(f"=> /collections/cartas/{next_section}/{next_name}.gmi {next_display} →")
            
            nav_lines.append("")
            nav_lines.append("---")
            nav_lines.append("")
            
            # Inserir navegação após o primeiro heading
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
            
            # Se não encontrou heading, adicionar no início
            if not first_heading_found:
                new_lines = nav_lines + new_lines
            
            updated_content = '\n'.join(new_lines)
            write_gmi_file(carta_path, updated_content)
    
    return sections_data

def build_index(pages: List[str], has_cartas: bool):
    """Gera index.gmi (home page)."""
    content = """# Krako

the Quantum Experimental Laboratories at 0xpblab — directory

A web1-style directory of interesting places on the internet.

This is a Gemini capsule.

"""
    
    if pages:
        content += "## Pages\n\n"
        for page in pages:
            content += f"=> /pages/{page}.gmi {page}\n"
        content += "\n"
    
    if has_cartas:
        content += "## Collections\n\n"
        content += "=> /collections/cartas/index.gmi Cartas para Pablo\n\n"
    
    write_gmi_file(CAPSULE_DIR / "index.gmi", content)
    print(f"[OK] Gerado index.gmi")

def main():
    """Função principal."""
    print("Iniciando build da capsule Gemini...\n")
    
    # Criar diretórios
    ensure_dir(CAPSULE_DIR)
    ensure_dir(PAGES_DIR)
    ensure_dir(COLLECTIONS_DIR)
    
    # Build páginas
    print("Convertendo paginas...")
    pages = build_pages()
    print()
    
    # Build coleção cartas
    print("Processando colecao cartas...")
    cartas_data = build_cartas_collection()
    print()
    
    # Build index
    print("Gerando index.gmi...")
    build_index(pages, cartas_data is not None)
    print()
    
    print("Build concluido!")
    print(f"Capsule gerada em: {CAPSULE_DIR.absolute()}")

if __name__ == "__main__":
    main()
