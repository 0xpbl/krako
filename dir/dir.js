const FILES_DIR = "./files/";
const FILES_TO_TRY = ["recomendati0n.txt"];

let FILES_LIST = [];
let CARTAS_LIST = [];
let CARTAS_METADATA = null;
let currentCartaIndex = -1;

let elListing = document.getElementById("listing");
const elToc = document.getElementById("toc");
const elFileIndex = document.getElementById("file-index");
const elErrorContainer = document.getElementById("error-container");
const elQ = document.getElementById("q");
const elClear = document.getElementById("clear");
const elListingOriginal = elListing;

let currentFile = "";
let rendered = "";

function slugify(s){
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function escapeHtml(s){
  return s.replace(/[&<>"']/g, (c) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  }[c]));
}

function isUrl(line){
  return /^https?:\/\/\S+$/i.test(line.trim());
}

function parseMarkdown(text){
  let html = text;
  
  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');
  
  // Links [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" rel="noreferrer noopener" target="_blank">$1</a>');
  
  // Horizontal rule
  html = html.replace(/^---$/gim, '<hr>');
  
  // Lists (basic support)
  html = html.replace(/^\- (.+)$/gim, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
  
  // Paragraphs (wrap consecutive non-header lines)
  const lines = html.split('\n');
  let result = [];
  let inParagraph = false;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) {
      if (inParagraph) {
        result.push('</p>');
        inParagraph = false;
      }
      result.push('');
      continue;
    }
    
    if (line.startsWith('<h') || line.startsWith('<ul') || line.startsWith('<li') || line.startsWith('<hr')) {
      if (inParagraph) {
        result.push('</p>');
        inParagraph = false;
      }
      result.push(line);
    } else {
      if (!inParagraph) {
        result.push('<p>');
        inParagraph = true;
      }
      result.push(line);
    }
  }
  
  if (inParagraph) {
    result.push('</p>');
  }
  
  html = result.join('\n');
  
  return html;
}

function parse(text, isMarkdown = false){
  if (isMarkdown) {
    const html = parseMarkdown(text);
    return [{ title: "Content", id: "content", items: [{ type: "html", html }] }];
  }
  
  const lines = text.replace(/\r\n/g, "\n").split("\n");

  let current = { title: "Unsorted", id: "unsorted", items: [] };
  const sections = [current];

  for (const raw of lines){
    const line = raw.trim();

    if (!line){
      current.items.push({ type: "blank" });
      continue;
    }

    if (line.startsWith("# ")){
      const title = line.slice(2).trim();
      const id = slugify(title) || "section";
      current = { title, id, items: [] };
      sections.push(current);
      continue;
    }

    if (isUrl(line)){
      current.items.push({ type: "link", url: line });
      continue;
    }

    current.items.push({ type: "text", text: raw });
  }

  return sections;
}

function render(sections){
  elToc.innerHTML = sections
    .filter(s => s.items.some(i => i.type !== "blank"))
    .map(s => `<a href="#${s.id}">${escapeHtml(s.title)}</a>`)
    .join("");

  const out = [];
  for (const s of sections){
    out.push(`\n== ${s.title} ==`);
    out.push(`[#${s.id}]\n`);
    for (const it of s.items){
      if (it.type === "blank"){
        out.push("");
      } else if (it.type === "text"){
        out.push(escapeHtml(it.text));
      } else if (it.type === "link"){
        const u = it.url;
        out.push(`<a href="${u}" rel="noreferrer noopener" target="_blank">${u}</a>`);
      } else if (it.type === "html"){
        out.push(it.html);
      }
    }
  }
  return out.join("\n");
}

function applyFilter(q){
  const query = (q || "").toLowerCase().trim();
  if (!query){
    elListing.innerHTML = rendered;
    return;
  }

  const lines = rendered.split("\n");
  const kept = lines.filter(l => l.toLowerCase().includes(query) || l.startsWith("== ") || l.startsWith("[#"));
  elListing.innerHTML = kept.join("\n");
}

function renderFileIndex(files, current){
  let html = files
    .map(f => {
      const isActive = f === current;
      const className = isActive ? "active" : "";
      return `<a href="#${f}" class="${className}" data-file="${f}">${escapeHtml(f)}</a>`;
    })
    .join("");
  
  // Add cartas collection if available
  if (CARTAS_LIST.length > 0 && CARTAS_METADATA) {
    const isCartasActive = current === "cartas";
    const cartasClass = isCartasActive ? "active" : "";
    html += ` <a href="#cartas" class="${cartasClass}" data-file="cartas">${escapeHtml(CARTAS_METADATA.mainMenuName || "cartas")}</a>`;
  }
  
  elFileIndex.innerHTML = html;
  
  // Add click handlers
  elFileIndex.querySelectorAll("a").forEach(a => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const file = a.getAttribute("data-file");
      if (file === "cartas") {
        loadCartasCollection();
      } else if (file && file !== currentFile) {
        loadFile(file);
      }
    });
  });
}

function createNekoIframe(containerId){
  const nekoHtml = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta http-equiv="Content-Security-Policy" content="script-src 'unsafe-inline' 'unsafe-eval' https://webneko.net; style-src 'unsafe-inline'; img-src https://webneko.net;">
  <script>NekoType="pink"</script>
</head>
<body style="margin:0;padding:10px;background:transparent;">
  <h1 id=nl style="margin:0;padding:0;"><script src="https://webneko.net/n20171213.js"></script><a href="https://webneko.net" style="color:#a7ffb5;text-decoration:none;">Neko</a></h1>
</body>
</html>`;
  
  const iframe = document.createElement("iframe");
  iframe.id = "neko-iframe";
  iframe.style.cssText = "border:none;width:100%;min-height:100px;background:transparent;";
  iframe.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  iframe.srcdoc = nekoHtml;
  
  const container = document.getElementById(containerId);
  if (container) {
    container.appendChild(iframe);
  }
  
  return iframe;
}

function showError(){
  elListing.style.display = "none";
  elErrorContainer.style.display = "block";
  
  elErrorContainer.innerHTML = `<p>oops, i don't know but look at the cat</p>`;
  createNekoIframe("error-container");
}

function showHomePage(){
  if (window.location.hash) {
    window.history.replaceState(null, '', window.location.pathname);
  }
  
  elErrorContainer.style.display = "none";
  elToc.innerHTML = "";
  elQ.value = "";
  currentFile = "";
  renderFileIndex(FILES_LIST, "");
  
  const parent = elListing.parentElement;
  if (elListing.id !== "listing") {
    // We're using a wrapper, restore the original
    parent.replaceChild(elListingOriginal, elListing);
    elListing = elListingOriginal;
  }
  
  elListing.style.display = "block";
  
  const randomContent = `welcome to the mildly organized pile

here you'll find a collection of internet oddities
curated with questionable taste and questionable methods

things that made someone go "hmm"
things that made someone go "why"
things that made someone go "what"

click on a file above to explore
or just stare at the cat for a while

the internet is weird
and that's okay`;

  const wrapper = document.createElement("div");
  wrapper.id = "home-content-wrapper";
  const textPre = document.createElement("pre");
  textPre.style.cssText = "margin:0;white-space:pre-wrap;word-break:break-word;line-height:1.45;";
  textPre.textContent = randomContent;
  wrapper.appendChild(textPre);
  
  const nekoContainer = document.createElement("div");
  nekoContainer.id = "home-neko-container";
  nekoContainer.style.cssText = "margin-top:20px;text-align:center;";
  wrapper.appendChild(nekoContainer);
  parent.replaceChild(wrapper, elListing);
  elListing = wrapper;
  createNekoIframe("home-neko-container");
}

async function loadFile(filename){
  currentFile = filename;
  const filePath = `${FILES_DIR}${filename}`;
  
  elErrorContainer.style.display = "none";
  const parent = elListing.parentElement;
  if (elListing.id !== "listing") {
    // We're using a wrapper, restore the original
    parent.replaceChild(elListingOriginal, elListing);
    elListing = elListingOriginal;
  }
  
  elListing.style.display = "block";
  elListing.textContent = `Loading ${filename}…`;
  
  const isFileProtocol = window.location.protocol === 'file:';
  if (isFileProtocol) {
    elListing.innerHTML = `
      <p style="color: var(--warn);">⚠️ Este site precisa ser servido via HTTP/HTTPS para funcionar.</p>
      <p style="color: var(--dim);">Use um servidor web local (ex: <code>python -m http.server</code> ou <code>npx serve</code>)</p>
      <p style="color: var(--dim);">Ou abra via: <code>http://localhost:8000/dir/index.html</code></p>
    `;
    return;
  }
  
  try {
    const res = await fetch(filePath, { cache: "no-store" });
    
    if (!res.ok) {
      showError();
      return;
    }
    const text = await res.text();

    const isMarkdown = filename.endsWith('.md');
    const sections = parse(text, isMarkdown);
    rendered = render(sections);
    elListing.innerHTML = rendered;
    renderFileIndex(FILES_LIST, currentFile);
    window.location.hash = filename;
    elQ.value = "";
    applyFilter("");
  } catch (err) {
    showError();
  }
}

async function discoverCartas(){
  const isFileProtocol = window.location.protocol === 'file:';
  
  if (isFileProtocol) {
    // For file protocol, assume cartas exist
    CARTAS_LIST = ["2000-04-06_moderate_reflections.md"];
    return;
  }
  
  try {
    // Load sections.json
    const metadataRes = await fetch(`${FILES_DIR}cartas/sections.json`, { cache: "no-store" });
    if (metadataRes.ok) {
      CARTAS_METADATA = await metadataRes.json();
    }
    
    // Try to discover files in cartas/random/
    // Since we can't list directory, we'll try a known pattern or use a manifest
    // For now, we'll try to fetch a few known files to confirm the directory exists
    const testFile = `${FILES_DIR}cartas/random/2000-04-06_moderate_reflections.md`;
    const testRes = await fetch(testFile, { method: "HEAD", cache: "no-store" });
    
    if (testRes.ok) {
      // Directory exists, we'll need to build the list from sections.json or discover dynamically
      // For now, we'll create a function that loads files on demand
      // We'll need to maintain a list - let's try to fetch a manifest or build it
      CARTAS_LIST = ["discover"]; // Special marker
    }
  } catch (err) {
    // Cartas not available
    CARTAS_LIST = [];
  }
}

async function loadCartasCollection(){
  currentFile = "cartas";
  elErrorContainer.style.display = "none";
  const parent = elListing.parentElement;
  if (elListing.id !== "listing") {
    parent.replaceChild(elListingOriginal, elListing);
    elListing = elListingOriginal;
  }
  
  elListing.style.display = "block";
  elListing.textContent = "Loading cartas...";
  
  const isFileProtocol = window.location.protocol === 'file:';
  if (isFileProtocol) {
    elListing.innerHTML = `
      <p style="color: var(--warn);">⚠️ Este site precisa ser servido via HTTP/HTTPS para funcionar.</p>
      <p style="color: var(--dim);">Use um servidor web local (ex: <code>python -m http.server</code> ou <code>npx serve</code>)</p>
    `;
    return;
  }
  
  try {
    // Load sections.json to get structure
    const metadataRes = await fetch(`${FILES_DIR}cartas/sections.json`, { cache: "no-store" });
    if (!metadataRes.ok) {
      showError();
      return;
    }
    
    CARTAS_METADATA = await metadataRes.json();
    
    // Build list of cartas by trying to fetch them
    // We'll use a known list pattern based on the files we saw
    const cartasFiles = [];
    const sections = CARTAS_METADATA.order || Object.keys(CARTAS_METADATA.sections || {});
    
    for (const section of sections) {
      // Try to discover files in this section
      // Since we can't list directories, we'll need to maintain a known list
      // For now, let's create a function that tries common patterns
      const sectionPath = `${FILES_DIR}cartas/${section}/`;
      
      // We'll need to maintain a list of known files or fetch a manifest
      // For simplicity, let's create a function that loads files on-demand
      cartasFiles.push({ section, path: sectionPath });
    }
    
    // Render the cartas index
    renderCartasIndex();
    renderFileIndex(FILES_LIST, "cartas");
    window.location.hash = "cartas";
    elQ.value = "";
  } catch (err) {
    showError();
  }
}

function renderCartasIndex(){
  if (!CARTAS_METADATA) {
    elListing.innerHTML = "<p>Cartas metadata not available</p>";
    return;
  }
  
  const sections = CARTAS_METADATA.order || Object.keys(CARTAS_METADATA.sections || {});
  let html = `<h1>${escapeHtml(CARTAS_METADATA.mainMenuName || "Cartas")}</h1>\n\n`;
  
  for (const section of sections) {
    const sectionName = CARTAS_METADATA.sections[section] || section;
    html += `<h2>${escapeHtml(sectionName)}</h2>\n`;
    html += `<p style="color: var(--dim);">Click on a carta to read it.</p>\n\n`;
    
    // We'll need to load the actual list of files
    // For now, create a placeholder that will be populated when files are discovered
    html += `<div id="cartas-list-${section}" style="margin: 10px 0;"></div>\n\n`;
  }
  
  elListing.innerHTML = html;
  
  // Try to discover and list cartas files (use setTimeout to ensure DOM is updated)
  setTimeout(() => {
    discoverCartasFiles();
  }, 0);
}

async function discoverCartasFiles(){
  // Known list of cartas files (we'll need to maintain this or fetch a manifest)
  // For now, let's try to fetch a few and build the list
  const knownFiles = [
    "2000-04-06_moderate_reflections.md",
    "2000-09-21_on_animals_and_humility.md",
    "2001-06-06_proud_of_their_gums.md",
    "2001-06-28_on_long_novels.md",
    "2001-07-25_boring_bird_talk.md",
    "2001-10-09_on_fences_and_property.md",
    "2001-10-09_the_gloucester_cheese_race.md",
    "2002-01-16_776_bc_at_the_olympics.md",
    "2002-02-08_stuffed_tiger_argument.md",
    "2002-03-07_telerj.md",
    "2002-04-09_grandpa_simpson_on_labels.md",
    "2002-04-19_sombreros_and_sophistication.md",
    "2002-09-11_the_horse_at_the_gates.md",
    "2003-02-24_helio_the_hermeneut.md",
    "2003-03-18_corporate_ear_muffs.md",
    "2003-07-21_conversation_starter_dolphin_bite.md",
    "2003-08-27_still_on_cetaceans.md",
    "2003-09-12_vikings_montaigne_and_a_fat_toad.md",
    "2004-01-05_super_pla_1969.md",
    "2004-04-06_icebreaker_alfredo_s_swim_briefs.md",
    "2004-04-20_pan_games_flash.md",
    "2004-12-03_christmas_tales_gdansk_or_kelvin.md",
    "2005-04-22_noise_proves_nothing.md",
    "2005-05-17_joel_stole_my_gibao.md",
    "2005-06-30_germany_vs_south_korea_broadcast.md",
    "2005-07-01_do_be_do_be_do.md",
    "2005-11-24_part_camel.md",
    "2005-12-14_ape_men_in_sweden.md",
    "2005-12-27_darfur_is_a_mess.md",
    "2006-06-30_restaurant_review_le_domaine_de_chateauvieux.md",
    "2006-09-12_after_watching_the_farm_a_fazenda.md",
    "2007-01-15_grandpa_simpson_s_onion_belt.md",
    "2007-04-12_breaking_news_badgers.md",
    "2007-06-01_tomatoes_once_poisonous.md",
    "2007-08-03_thailand_s_petition_husband.md",
    "2008-01-21_san_marino_gdp_shares_1952.md",
    "2008-05-23_pigeons_and_peace.md",
    "2009-03-23_moustache_as_collateral.md",
    "2009-05-29_official_city_drunk.md",
    "2010-01-29_the_disguised_gorilla.md",
    "2010-02-17_amapa_s_26_guinea_fowl.md",
    "2010-04-23_an_aparicio_on_the_pitch.md",
    "2010-05-19_notable_birthdays_june_7.md",
    "2010-08-12_presidents_of_gabon.md",
    "2010-08-31_cone_before_ice_cream.md",
    "2010-10-20_rejected_samba_north_korea.md",
    "2010-11-22_pablo_escobar_samba.md",
    "2011-04-14_tsetse_fly_chorus.md",
    "2011-05-25_hydrogenated_fat_parade.md",
    "2011-11-03_smell_of_uranium.md",
    "2011-11-15_pluto_the_dwarf_planet.md",
    "2011-11-25_catheterization_samba.md",
    "2011-12-14_male_nipple_question.md",
    "2012-02-17_237_reasons_for_the_old_days.md",
    "2012-03-27_in_praise_of_human_lard.md",
    "2012-05-07_borrowing_an_eraser.md",
    "2013-03-15_ivo_who_saw_the_grape.md",
    "2013-05-08_ghost_included_in_the_price.md",
    "2013-07-04_buying_a_flea.md",
    "2014-01-29_small_talk_across_species.md",
    "2014-02-07_more_coffee_kofi.md",
    "2014-03-31_small_talk_with_an_epidemiologist.md",
    "2014-05-07_small_talk_with_an_occupational_therapist.md",
    "2014-07-01_small_talk_with_a_frog_man.md",
    "2014-07-31_community_idea_voluptuous_pea.md",
    "2014-09-15_community_idea_chrysippus_died_laughing.md",
    "2015-01-14_community_idea_smoked_herring.md",
    "2015-01-26_community_idea_sausage_events.md",
    "2015-06-10_community_idea_the_great_stoat_revolution.md",
    "2015-08-18_community_idea_the_greatest_tourniquet.md",
    "2015-08-31_community_idea_nelson_the_bearded_lady.md",
    "2015-11-18_community_idea_obscure_biblical_characters.md",
    "2016-02-23_community_idea_barry_pepper_and_the_dolphin.md",
    "2016-03-24_community_idea_pure_corn_starch.md",
    "2016-05-03_community_idea_better_english_than_hugh_grant.md",
    "2016-05-17_community_idea_edecarlos_law_yer.md",
    "2016-07-04_community_idea_cured_by_citrus.md"
  ];
  
  const sections = CARTAS_METADATA.order || Object.keys(CARTAS_METADATA.sections || {});
  const section = sections[0] || "random";
  
  let html = "";
  const sortedFiles = knownFiles.sort();
  
  for (const filename of sortedFiles) {
    const displayName = filename.replace(/\.md$/, "").replace(/_/g, " ");
    html += `<a href="#carta:${section}/${filename}" style="display: block; margin: 5px 0; color: var(--accent); text-decoration: none;" data-carta="${section}/${filename}">${escapeHtml(displayName)}</a>\n`;
  }
  
  const listContainer = document.getElementById(`cartas-list-${section}`);
  if (listContainer) {
    listContainer.innerHTML = html;
    
    // Add click handlers
    listContainer.querySelectorAll("a[data-carta]").forEach(a => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const cartaPath = a.getAttribute("data-carta");
        loadCarta(cartaPath);
      });
    });
  }
  
  CARTAS_LIST = knownFiles.map(f => `${section}/${f}`);
}

async function loadCarta(cartaPath){
  const [section, filename] = cartaPath.split("/");
  const filePath = `${FILES_DIR}cartas/${section}/${filename}`;
  
  elErrorContainer.style.display = "none";
  const parent = elListing.parentElement;
  if (elListing.id !== "listing") {
    parent.replaceChild(elListingOriginal, elListing);
    elListing = elListingOriginal;
  }
  
  elListing.style.display = "block";
  elListing.textContent = `Loading ${filename}…`;
  
  const isFileProtocol = window.location.protocol === 'file:';
  if (isFileProtocol) {
    elListing.innerHTML = `
      <p style="color: var(--warn);">⚠️ Este site precisa ser servido via HTTP/HTTPS para funcionar.</p>
    `;
    return;
  }
  
  try {
    const res = await fetch(filePath, { cache: "no-store" });
    
    if (!res.ok) {
      showError();
      return;
    }
    const text = await res.text();
    
    const sections = parse(text, true); // Markdown
    rendered = render(sections);
    
    // Add navigation
    const currentIndex = CARTAS_LIST.indexOf(cartaPath);
    let navHtml = "";
    
    if (currentIndex > 0) {
      const prevPath = CARTAS_LIST[currentIndex - 1];
      const prevName = prevPath.split("/").pop().replace(/\.md$/, "").replace(/_/g, " ");
      navHtml += `<a href="#carta:${prevPath}" style="color: var(--accent); text-decoration: none; margin-right: 20px;" data-carta="${prevPath}">← ${escapeHtml(prevName)}</a>`;
    }
    
    navHtml += `<a href="#cartas" style="color: var(--accent); text-decoration: none; margin: 0 20px;">↑ Voltar</a>`;
    
    if (currentIndex < CARTAS_LIST.length - 1) {
      const nextPath = CARTAS_LIST[currentIndex + 1];
      const nextName = nextPath.split("/").pop().replace(/\.md$/, "").replace(/_/g, " ");
      navHtml += `<a href="#carta:${nextPath}" style="color: var(--accent); text-decoration: none; margin-left: 20px;" data-carta="${nextPath}">${escapeHtml(nextName)} →</a>`;
    }
    
    elListing.innerHTML = `<div style="margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px dashed var(--line);">${navHtml}</div>\n${rendered}`;
    
    // Add click handlers for navigation
    elListing.querySelectorAll("a[data-carta]").forEach(a => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const path = a.getAttribute("data-carta");
        loadCarta(path);
      });
    });
    
    currentCartaIndex = currentIndex;
    renderFileIndex(FILES_LIST, "cartas");
    window.location.hash = `carta:${cartaPath}`;
    elQ.value = "";
    applyFilter("");
  } catch (err) {
    showError();
  }
}

async function discoverFiles(){
  const discoveredFiles = [];
  const isFileProtocol = window.location.protocol === 'file:';
  
  if (isFileProtocol) {
    FILES_LIST = FILES_TO_TRY;
    await discoverCartas();
    return;
  }
  
  const filesToCheck = [...FILES_TO_TRY];
  const checks = filesToCheck.map(async (filename) => {
    try {
      const filePath = `${FILES_DIR}${filename}`;
      let res = await fetch(filePath, { method: "HEAD", cache: "no-store" }).catch(() => null);
      if (!res || !res.ok) {
        res = await fetch(filePath, { method: "GET", cache: "no-store" });
      }
      if (res.ok) {
        return filename;
      }
    } catch (err) {
    }
    return null;
  });
  
  const results = await Promise.allSettled(checks);
  results.forEach((result) => {
    if (result.status === "fulfilled" && result.value) {
      discoveredFiles.push(result.value);
    }
  });
  
  FILES_LIST = discoveredFiles.length > 0 ? discoveredFiles : FILES_TO_TRY;
  
  // Discover cartas
  await discoverCartas();
}

async function main(){
  await discoverFiles();
  renderFileIndex(FILES_LIST, "");
  
  const hash = window.location.hash.slice(1);
  
  if (hash === "cartas") {
    await loadCartasCollection();
  } else if (hash.startsWith("carta:")) {
    const cartaPath = hash.slice(6); // Remove "carta:" prefix
    await loadCarta(cartaPath);
  } else if (hash && FILES_LIST.includes(hash)) {
    await loadFile(hash);
  } else {
    if (hash) {
      window.history.replaceState(null, '', window.location.pathname);
    }
    showHomePage();
  }

  elQ.addEventListener("input", () => applyFilter(elQ.value));
  elClear.addEventListener("click", () => {
    elQ.value = "";
    applyFilter("");
    elQ.focus();
  });

  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.slice(1);
    if (hash === "cartas") {
      loadCartasCollection();
    } else if (hash.startsWith("carta:")) {
      const cartaPath = hash.slice(6);
      loadCarta(cartaPath);
    } else if (hash && FILES_LIST.includes(hash) && hash !== currentFile) {
      loadFile(hash);
    } else if (!hash) {
      showHomePage();
    }
  });
}

main().catch(err => {
  showError();
});
