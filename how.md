# Como o projeto tilt funciona

Este documento explica o funcionamento interno do diretório web1-style **tilt**, desenvolvido pelos Quantum Experimental Laboratories at 0xpblab.

## Visão geral

O **tilt** é uma aplicação web minimalista que exibe uma coleção de links interessantes da internet em formato de diretório. Ele funciona como um visualizador de arquivos de texto formatados e markdown, transformando listas simples em uma interface navegável com filtros e seções. O projeto também suporta coleções de arquivos, como a pasta "cartas" com documentos markdown navegáveis.

## Arquitetura

### Estrutura de arquivos

```
tilt/
├── dir/
│   ├── index.html      # Página principal
│   ├── dir.js          # Lógica JavaScript
│   ├── dir.css         # Estilos
│   └── files/          # Arquivos de dados
│       ├── recomendati0n.txt
│       ├── index.txt
│       └── cartas/      # Coleção de cartas
│           ├── sections.json
│           └── random/  # 77 arquivos .md
└── README.md
```

### Componentes principais

1. **HTML (`index.html`)**: Estrutura da página com banner ASCII, controles de filtro e área de conteúdo
2. **JavaScript (`dir.js`)**: Toda a lógica de funcionamento, incluindo parsing de markdown e navegação de coleções
3. **CSS (`dir.css`)**: Estilos retro/terminal com tema escuro
4. **Arquivos de dados (`files/*.txt`)**: Listas de links formatadas
5. **Coleções (`files/cartas/`)**: Estrutura hierárquica de arquivos markdown com metadados

## Fluxo de funcionamento

### 1. Inicialização

Quando a página carrega, o JavaScript executa a função `main()`:

```javascript
async function main() {
  await discoverFiles();        // Descobre arquivos disponíveis
  await discoverCartas();       // Descobre coleção de cartas
  renderFileIndex(FILES_LIST, "");  // Renderiza índice de arquivos
  
  // Verifica se há hash na URL (#filename ou #cartas ou #carta:path)
  const hash = window.location.hash.slice(1);
  
  if (hash === "cartas") {
    await loadCartasCollection();  // Carrega coleção de cartas
  } else if (hash.startsWith("carta:")) {
    await loadCarta(hash.slice(6));  // Carrega carta específica
  } else if (hash && FILES_LIST.includes(hash)) {
    await loadFile(hash);       // Carrega arquivo específico
  } else {
    showHomePage();             // Mostra página inicial
  }
  
  // Configura event listeners
  elQ.addEventListener("input", () => applyFilter(elQ.value));
  elClear.addEventListener("click", () => { /* ... */ });
  
  window.addEventListener("hashchange", () => { /* ... */ });
}
```

### 2. Descoberta de arquivos

A função `discoverFiles()` verifica quais arquivos existem na pasta `files/`:

- Tenta fazer requisições HEAD/GET para cada arquivo em `FILES_TO_TRY`
- Se estiver usando protocolo `file://`, usa a lista padrão sem verificação
- Armazena os arquivos encontrados em `FILES_LIST`
- Chama `discoverCartas()` para descobrir a coleção de cartas

### 3. Descoberta de coleções (Cartas)

A função `discoverCartas()` verifica se a coleção de cartas está disponível:

- Tenta carregar `files/cartas/sections.json` para obter metadados
- Verifica se a estrutura de pastas existe (testando um arquivo conhecido)
- Armazena metadados em `CARTAS_METADATA` e lista de arquivos em `CARTAS_LIST`
- A coleção aparece como uma entrada especial no índice de arquivos

### 4. Carregamento de arquivos

Quando um arquivo é selecionado, `loadFile(filename)`:

1. Detecta se é um arquivo markdown (extensão `.md`)
2. Faz fetch do arquivo via `fetch(filePath)`
3. Chama `parse(text, isMarkdown)` para processar o conteúdo
4. Chama `render(sections)` para gerar HTML
5. Atualiza o DOM e o índice de arquivos
6. Atualiza o hash da URL para permitir compartilhamento

### 5. Carregamento de coleções

Quando a coleção "cartas" é selecionada, `loadCartasCollection()`:

1. Carrega `sections.json` para obter estrutura e metadados
2. Chama `renderCartasIndex()` para exibir lista de cartas
3. Chama `discoverCartasFiles()` para descobrir e listar todos os arquivos
4. Cria links clicáveis para cada carta
5. Permite navegação entre cartas

### 6. Carregamento de cartas individuais

Quando uma carta específica é selecionada, `loadCarta(cartaPath)`:

1. Faz fetch do arquivo markdown na pasta `cartas/{section}/{filename}`
2. Processa o markdown com `parseMarkdown()`
3. Renderiza o conteúdo formatado
4. Adiciona navegação (anterior/próxima) entre cartas
5. Atualiza o hash da URL com formato `#carta:section/filename`

### 7. Parsing de arquivos

A função `parse(text, isMarkdown)` processa o conteúdo:

**Para arquivos de texto (.txt):**
- **Seções**: Linhas começando com `# Título` criam novas seções
- **URLs**: Linhas que são URLs válidas (começam com `http://` ou `https://`) viram links
- **Texto**: Qualquer outra linha é preservada como texto simples
- **Linhas vazias**: São mantidas para espaçamento

**Para arquivos markdown (.md):**
- Usa a função `parseMarkdown()` para converter markdown em HTML
- Suporta títulos, negrito, itálico, links, listas, regras horizontais

**Exemplo de arquivo .txt:**
```
# Arquivos Web
https://archive.org
https://textfiles.com

# Comunidades
https://neocities.org
Um site interessante sobre web indie
```

**Exemplo de arquivo .md:**
```markdown
# Título Principal

## Subtítulo

Este é um parágrafo com **negrito** e *itálico*.

- Item de lista 1
- Item de lista 2

[Link para site](https://exemplo.com)
```

### 8. Parser de Markdown

A função `parseMarkdown(text)` converte markdown básico para HTML:

**Recursos suportados:**
- **Títulos**: `# H1`, `## H2`, `### H3`
- **Negrito**: `**texto**` ou `__texto__`
- **Itálico**: `*texto*` ou `_texto_`
- **Links**: `[texto](url)`
- **Regras horizontais**: `---`
- **Listas**: Linhas começando com `-`
- **Parágrafos**: Texto contínuo é agrupado em parágrafos

**Exemplo de conversão:**
```markdown
# Título
**Negrito** e *itálico*
[Link](https://exemplo.com)
```

Converte para:
```html
<h1>Título</h1>
<p><strong>Negrito</strong> e <em>itálico</em></p>
<p><a href="https://exemplo.com">Link</a></p>
```

### 9. Renderização

A função `render(sections)` gera o HTML formatado:

- Cria uma tabela de conteúdos (TOC) com links para cada seção
- Gera o conteúdo formatado com:
  - Cabeçalhos de seção: `== Título ==` e `[#id]` (para arquivos .txt)
  - HTML renderizado (para arquivos .md)
  - Links clicáveis para URLs
  - Texto escapado (proteção XSS)

### 10. Sistema de filtro

O filtro funciona em tempo real:

1. Usuário digita no campo de busca
2. `applyFilter(query)` é chamado
3. Filtra linhas que contêm o termo de busca (case-insensitive)
4. Mantém sempre cabeçalhos de seção (`== ` e `[#`)
5. Atualiza o DOM com resultado filtrado

**Nota**: O filtro funciona melhor com arquivos .txt. Para arquivos markdown renderizados, o filtro pode não funcionar perfeitamente devido ao HTML gerado.

### 11. Navegação

O projeto usa **hash navigation** com três tipos de URLs:

- **Arquivos simples**: `#recomendati0n.txt` - carrega arquivo específico
- **Coleções**: `#cartas` - carrega índice da coleção
- **Itens de coleção**: `#carta:random/2000-04-06_moderate_reflections.md` - carrega item específico

O evento `hashchange` detecta mudanças na URL e carrega o conteúdo apropriado. Isso permite compartilhar links diretos para arquivos, coleções ou itens específicos.

## Funcionalidades especiais

### Página inicial

Quando não há arquivo selecionado, `showHomePage()` exibe:
- Mensagem de boas-vindas
- Gato animado (Neko) via iframe
- Índice de arquivos disponíveis (incluindo coleções)

### Coleções de arquivos

O sistema suporta coleções hierárquicas de arquivos:

**Estrutura de uma coleção:**
```
files/cartas/
├── sections.json    # Metadados da coleção
└── random/          # Seção da coleção
    ├── arquivo1.md
    ├── arquivo2.md
    └── ...
```

**Formato de `sections.json`:**
```json
{
  "mainMenuName": "Cartas para Pablo",
  "sections": {
    "random": "Insane Letters"
  },
  "order": ["random"]
}
```

**Funcionalidades:**
- Índice navegável de todos os itens da coleção
- Navegação entre itens (anterior/próxima)
- Renderização automática de markdown
- Links diretos para itens específicos

### Tratamento de erros

Se um arquivo não pode ser carregado:
- `showError()` é chamado
- Exibe mensagem "oops, i don't know but look at the cat"
- Mostra gato animado para entretenimento

### Integração Neko

O projeto integra um gato animado de `webneko.net`:
- Criado via iframe com sandbox para segurança
- Aparece na página inicial e em erros
- Configurado com tipo "pink"

### Detecção de protocolo

O código detecta se está rodando via `file://`:
- Mostra aviso para usar servidor HTTP
- Sugere comandos como `python -m http.server` ou `npx serve`
- Funcionalidade limitada em modo file://

## Variáveis globais importantes

```javascript
const FILES_DIR = "./files/";           // Diretório dos arquivos
const FILES_TO_TRY = ["recomendati0n.txt"];  // Arquivos padrão
let FILES_LIST = [];                    // Lista de arquivos descobertos
let CARTAS_LIST = [];                   // Lista de cartas descobertas
let CARTAS_METADATA = null;             // Metadados da coleção de cartas
let currentCartaIndex = -1;              // Índice da carta atual
let currentFile = "";                    // Arquivo atual
let rendered = "";                      // HTML renderizado (para filtro)
```

## Funções auxiliares

- **`slugify(s)`**: Converte texto em slug (ex: "Arquivos Web" → "arquivos-web")
- **`escapeHtml(s)`**: Escapa caracteres HTML para prevenir XSS
- **`isUrl(line)`**: Verifica se uma linha é uma URL válida
- **`parseMarkdown(text)`**: Converte markdown básico para HTML

## Funções de coleções

- **`discoverCartas()`**: Descobre e carrega metadados da coleção de cartas
- **`loadCartasCollection()`**: Carrega e exibe o índice da coleção
- **`renderCartasIndex()`**: Renderiza a lista de cartas disponíveis
- **`discoverCartasFiles()`**: Descobre todos os arquivos de cartas
- **`loadCarta(cartaPath)`**: Carrega uma carta específica com navegação

## Como adicionar novos arquivos

### Arquivos simples (.txt)

1. Crie um arquivo `.txt` na pasta `files/`
2. Adicione o nome do arquivo em `FILES_TO_TRY` no `dir.js`:
   ```javascript
   const FILES_TO_TRY = ["recomendati0n.txt", "seu-arquivo.txt"];
   ```
3. O sistema descobrirá automaticamente o arquivo na próxima carga

### Arquivos Markdown (.md)

1. Crie um arquivo `.md` na pasta `files/`
2. Adicione o nome do arquivo em `FILES_TO_TRY` no `dir.js`
3. O sistema detectará automaticamente a extensão `.md` e renderizará como markdown

### Coleções de arquivos

1. Crie uma pasta dentro de `files/` (ex: `files/minha-colecao/`)
2. Crie um arquivo `sections.json` com a estrutura:
   ```json
   {
     "mainMenuName": "Nome da Coleção",
     "sections": {
       "secao1": "Nome da Seção 1"
     },
     "order": ["secao1"]
   }
   ```
3. Adicione arquivos nas subpastas correspondentes
4. Modifique `discoverCartas()` ou crie uma função similar para sua coleção
5. Adicione a lógica de descoberta em `discoverFiles()`

## Formato recomendado para arquivos

### Arquivos .txt

```txt
# Título da Seção 1

https://exemplo.com
https://outro-site.com
Texto descritivo opcional

# Título da Seção 2

https://mais-um-link.com
```

### Arquivos .md

```markdown
# Título Principal

## Subtítulo

Parágrafo com **negrito** e *itálico*.

- Item de lista
- Outro item

[Link](https://exemplo.com)
```

### Estrutura de coleções

```
files/colecao/
├── sections.json
└── secao1/
    ├── arquivo1.md
    └── arquivo2.md
```

## Segurança

- **CSP (Content Security Policy)**: Configurado no HTML para mitigar XSS
- **Escape HTML**: Todo texto do usuário é escapado antes de inserir no DOM
- **Sandbox iframe**: O iframe do Neko usa sandbox para isolamento
- **rel="noreferrer noopener"**: Links externos usam atributos de segurança
- **Validação de markdown**: O parser de markdown é limitado e não executa código

## Estilos e tema

O CSS usa variáveis CSS para cores:
- `--bg`: Fundo escuro (#0b0f0c)
- `--fg`: Texto principal (#d7ffd7)
- `--accent`: Cor de destaque para links (#a7ffb5)
- `--dim`: Texto secundário (#93c79a)
- `--line`: Cor de bordas (rgba(215,255,215,0.12))
- `--warn`: Cor de avisos (#ffdd88)
- Efeito de scanline via `repeating-linear-gradient`

## Dependências externas

- **webneko.net**: Serviço externo para gato animado (carregado via iframe)

## Compatibilidade

- Funciona em navegadores modernos com suporte a:
  - Fetch API
  - ES6+ (async/await, arrow functions, template literals)
  - CSS Variables
  - Hash navigation

## Limitações

- Requer servidor HTTP (não funciona completamente com `file://`)
- Arquivos devem estar na pasta `files/` relativa ao HTML
- URLs devem começar com `http://` ou `https://` para serem detectadas
- O parser de markdown é básico e não suporta todos os recursos do markdown completo
- Lista de cartas precisa ser mantida manualmente ou via manifest (não há listagem automática de diretórios)
- O filtro funciona melhor com arquivos .txt do que com markdown renderizado

## Exemplos de uso

### Navegar para um arquivo
```
http://localhost:8000/dir/index.html#recomendati0n.txt
```

### Navegar para uma coleção
```
http://localhost:8000/dir/index.html#cartas
```

### Navegar para um item específico de uma coleção
```
http://localhost:8000/dir/index.html#carta:random/2000-04-06_moderate_reflections.md
```

---

*Desenvolvido por pmurad para os Quantum Experimental Laboratories at 0xpblab*
