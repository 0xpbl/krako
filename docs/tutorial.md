# Tutorial: como atualizar o Krako (Gemini) na VPS

Este guia assume:
- VPS Debian 12
- Capsule Gemini servida pelo **Agate** via systemd (`krako-gemini.service`)
- Conteúdo publicado em: `/var/lib/krako/content`
- Fontes do projeto (repo Krako) em: `~/krako` (ou outro diretório equivalente)

## 1) Conceitos rápidos

### O que o Agate serve
O Agate serve **arquivos estáticos**. No seu setup, ele publica tudo que estiver em:

- `/var/lib/krako/content`

Para diretórios, ele procura `index.gmi`.

### O que muda quando você edita Markdown
Você tem dois cenários possíveis:

1. **Publicar Markdown “cru” (sem converter/renderizar)**
   - Você quer colocar `.md` no servidor e que o Gemini entregue exatamente o texto do `.md`.
   - Isso funciona, mas o cliente Gemini vai exibir como texto simples (não como HTML).

2. **Converter Markdown para Gemtext** (o modo atual do build)
   - Seu script (`build_capsule.py`) converte `.md` → `.gmi` e gera índices.
   - É o modo que dá melhor experiência em Gemini.

Este tutorial cobre **os dois**.

---

## 2) Modo A — Atualizar páginas mantendo Markdown “cru” (sem converter)

### Quando usar
- Você quer velocidade e simplicidade.
- Não precisa de índices automáticos ou links no formato `=>`.
- Aceita que o conteúdo será mostrado como texto puro.

### Estrutura recomendada
Dentro de `/var/lib/krako/content` crie um diretório para markdown, por exemplo:

- `/var/lib/krako/content/md/`

Exemplos:
- `/var/lib/krako/content/md/notes.md`
- `/var/lib/krako/content/md/changelog.md`

### Publicando um novo arquivo
1) Copie o arquivo `.md` para o servidor:

```bash
# no seu computador (origem)
rsync -a ./notes.md root@SUA_VPS:/var/lib/krako/content/md/
```

2) Ajuste permissões (na VPS):

```bash
chown -R krako:krako /var/lib/krako/content/md
```

3) Linke no Gemini (edite um arquivo `.gmi` existente, por exemplo o `index.gmi`):

```text
=> /md/notes.md Notes (Markdown)
```

### Observações importantes
- O tipo MIME pode aparecer como `text/plain` dependendo do servidor; Gemini não “renderiza” markdown.
- Para melhor navegação, você normalmente quer colocar links Gemtext em `.gmi`, mesmo que o conteúdo final seja `.md`.

---

## 3) Modo B — Atualizar normalmente (convertendo para Gemtext) — recomendado

### Quando usar
- Você quer o conteúdo com melhor UX em Gemini.
- Quer índices e organização coerentes.
- Quer que links virem `=>` automaticamente.

### Fluxo padrão de atualização
1) Entre na pasta do projeto:

```bash
cd ~/krako
```

2) Edite seus arquivos fonte (`.txt` e/ou `.md`)

3) Rode o build:

```bash
python3 build_capsule.py
```

4) Publique a capsule gerada para o diretório servido:

```bash
rsync -a --delete ~/krako/capsule/ /var/lib/krako/content/
chown -R krako:krako /var/lib/krako/content
```

5) (Opcional) Reiniciar o serviço
Na maioria dos casos **não é necessário** reiniciar; o Agate serve arquivos diretamente do disco. Mas se você quiser garantir:

```bash
systemctl restart krako-gemini
```

---

## 4) Modo C — Atualizar só um arquivo (rápido)

Se você só mexeu em um arquivo e quer uma atualização rápida:

1) Rode o build mesmo assim (para manter índices consistentes):

```bash
cd ~/krako
python3 build_capsule.py
```

2) Sincronize apenas a subpasta que mudou. Exemplo para páginas:

```bash
rsync -a --delete ~/krako/capsule/pages/ /var/lib/krako/content/pages/
chown -R krako:krako /var/lib/krako/content/pages
```

Para a coleção de cartas:

```bash
rsync -a --delete ~/krako/capsule/collections/cartas/ /var/lib/krako/content/collections/cartas/
chown -R krako:krako /var/lib/krako/content/collections/cartas
```

---

## 5) Conferência pós-deploy

### Verificar se o serviço está ativo
```bash
systemctl status krako-gemini --no-pager
```

### Verificar se está escutando na porta 1965
```bash
ss -lntp | grep 1965 || true
```

### Teste local TLS (retorna `20 text/gemini`)
```bash
echo "gemini://gemini.pablo.space/" | \
openssl s_client -connect 127.0.0.1:1965 -servername gemini.pablo.space -crlf -quiet
```

---

## 6) Automação opcional (para evitar trabalho manual)

### Script de deploy
Crie `/usr/local/bin/krako-deploy.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd ~/krako
python3 build_capsule.py
rsync -a --delete ./capsule/ /var/lib/krako/content/
chown -R krako:krako /var/lib/krako/content
```

Ative:

```bash
chmod +x /usr/local/bin/krako-deploy.sh
```

Use:

```bash
/usr/local/bin/krako-deploy.sh
```

---

## 7) Recomendação prática
- Se você quer “atualizar páginas” mantendo uma experiência Gemini consistente: use **Modo B** (convertendo `.md` para `.gmi`).
- Se você quer publicar textos rápidos e não se importa com UX: use **Modo A** (servir `.md` como texto cru) e linkar a partir de `.gmi`.

Se você me disser onde ficam exatamente seus arquivos fonte (pasta e convenção), eu adapto os comandos do tutorial para o seu layout real do Krako (pages/cartas/etc.) e incluo um script de deploy já com paths definitivos.


rsync -a --delete ~/krako/capsule/ /var/lib/krako/content/
chown -R krako:krako /var/lib/krako/content
