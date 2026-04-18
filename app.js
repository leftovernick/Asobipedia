(function () {
  const data = window.MONSTER_VIEWER_DATA;
  if (!data || !Array.isArray(data.monsters)) {
    throw new Error("Monster viewer data is missing.");
  }

  const elements = {
    count: document.getElementById("monster-count"),
    search: document.getElementById("search-input"),
    list: document.getElementById("monster-list"),
    id: document.getElementById("monster-id"),
    name: document.getElementById("monster-name"),
    identifier: document.getElementById("monster-identifier"),
    types: document.getElementById("monster-types"),
    description: document.getElementById("monster-description"),
    shapeIcon: document.getElementById("monster-shape-icon"),
    shapeName: document.getElementById("monster-shape-name"),
    overview: document.getElementById("overview-grid"),
    behavior: document.getElementById("monster-behavior"),
    habitat: document.getElementById("monster-habitat"),
    trivia: document.getElementById("monster-trivia"),
    abilities: document.getElementById("abilities-list"),
    abilityDetail: document.getElementById("ability-detail"),
    abilityDetailName: document.getElementById("ability-detail-name"),
    abilityDetailText: document.getElementById("ability-detail-text"),
    stats: document.getElementById("stats-list"),
    learnset: document.getElementById("learnset-body"),
    frontFrame: document.getElementById("monster-front-frame"),
    backFrame: document.getElementById("monster-back-frame"),
  };

  const state = {
    filtered: [...data.monsters],
    selectedSlug: data.monsters[0] ? data.monsters[0].slug : null,
    selectedAbilityName: null,
  };

  const TYPE_ICON_PREFIX = "../../source/images/icons/";
  const TYPE_ICON_SUFFIX = "Icon.png";
  const TILE_SIZE = 128;

  function formatRate(rate) {
    if (rate === null || rate === undefined || Number.isNaN(Number(rate))) {
      return "Rate n/a";
    }
    return `${rate}% roll`;
  }

  function normalizeLoreValue(value, fallback) {
    if (Array.isArray(value)) {
      const entries = value
        .map((entry) => String(entry || "").trim())
        .filter(Boolean);
      return entries.length > 0 ? entries.join("\n\n") : fallback;
    }

    const text = String(value || "").trim();
    return text ? text : fallback;
  }

  function typeIconPath(typeName) {
    return `${TYPE_ICON_PREFIX}${typeName.toLowerCase()}${TYPE_ICON_SUFFIX}`;
  }

  function normalizeShapeName(shapeName) {
    if (!shapeName) {
      return "";
    }

    const trimmed = String(shapeName).trim();
    return trimmed.charAt(0).toLowerCase() + trimmed.slice(1);
  }

  function formatShapeLabel(shapeName) {
    if (!shapeName) {
      return "Unknown";
    }

    return String(shapeName)
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function renderShape(monster) {
    const rawShape = monster.shape || "";
    const label = formatShapeLabel(rawShape);

    elements.shapeName.textContent = label || "Unknown";
    elements.shapeIcon.alt = `${label || "Unknown"} shape icon`;

    if (monster.shapeIcon) {
      elements.shapeIcon.src = monster.shapeIcon;
      elements.shapeIcon.style.display = "block";
    } else {
      elements.shapeIcon.removeAttribute("src");
      elements.shapeIcon.style.display = "none";
    }
  }

  function createTypePill(typeName) {
    const pill = document.createElement("div");
    pill.className = "type-pill";

    const icon = document.createElement("img");
    icon.src = typeIconPath(typeName);
    icon.alt = `${typeName} icon`;
    icon.onerror = () => {
      icon.style.display = "none";
    };

    const label = document.createElement("span");
    label.textContent = typeName;

    pill.append(icon, label);
    return pill;
  }

  function renderList() {
    elements.list.innerHTML = "";
    state.filtered.forEach((monster) => {
      const button = document.createElement("button");
      button.className = "monster-button";
      if (monster.slug === state.selectedSlug) {
        button.classList.add("active");
      }

      const nameRow = document.createElement("div");
      nameRow.className = "name-row";
      nameRow.innerHTML = `<span>${monster.name}</span><span>#${String(monster.id).padStart(3, "0")}</span>`;

      const metaRow = document.createElement("div");
      metaRow.className = "meta-row";
      metaRow.textContent = `${monster.identifier} | ${monster.types.join(" / ")}`;

      button.append(nameRow, metaRow);
      button.addEventListener("click", () => {
        state.selectedSlug = monster.slug;
        render();
      });

      elements.list.appendChild(button);
    });
  }

  function renderOverview(monster) {
    const cards = [
      ["Height", monster.height],
      ["Weight", monster.weight],
      ["BST", monster.bst],
      ["Base Mana", monster.baseStats.mana],
      ["Catch Rate", monster.catchRate],
      ["Exp Yield", monster.experienceYield],
      ["Level Rate", monster.levelingRate],
      ["DV", `${monster.dvType} +${monster.dvYield}`],
      ["Tags", monster.tags || "None"],
      ["Male %", monster.maleChance],
    ];

    elements.overview.innerHTML = "";
    cards.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "overview-card";
      card.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
      elements.overview.appendChild(card);
    });
  }

  function renderLore(monster) {
    elements.behavior.textContent = normalizeLoreValue(monster.behavior, "No behavior entry recorded yet.");
    elements.habitat.textContent = normalizeLoreValue(monster.habitat, "No habitat entry recorded yet.");
    elements.trivia.textContent = normalizeLoreValue(monster.trivia, "No trivia entry recorded yet.");
  }

  function renderAbilities(monster) {
    elements.abilities.innerHTML = "";
    const selectedAbility = monster.abilities.find((ability) => ability.name === state.selectedAbilityName)
      || monster.abilities[0]
      || null;
    state.selectedAbilityName = selectedAbility ? selectedAbility.name : null;

    monster.abilities.forEach((ability) => {
      const chip = document.createElement("div");
      chip.className = "ability-chip";
       if (selectedAbility && selectedAbility.name === ability.name) {
        chip.classList.add("active");
      }
      chip.innerHTML = `<div>${ability.name}</div><div class="rate">${formatRate(ability.rate)}</div>`;
      chip.addEventListener("click", () => {
        state.selectedAbilityName = ability.name;
        renderAbilities(monster);
      });
      elements.abilities.appendChild(chip);
    });

    if (selectedAbility) {
      elements.abilityDetailName.textContent = selectedAbility.name;
      elements.abilityDetailText.textContent = selectedAbility.description || "No description found.";
    } else {
      elements.abilityDetailName.textContent = "No abilities";
      elements.abilityDetailText.textContent = "This monster has no ability data to display.";
    }
  }

  function renderStats(monster) {
    elements.stats.innerHTML = "";
    const statDefs = [
      ["HP", monster.baseStats.hp],
      ["Mana", monster.baseStats.mana],
      ["Attack", monster.baseStats.attack],
      ["Defence", monster.baseStats.defence],
      ["Sp. Atk", monster.baseStats.specialAttack],
      ["Sp. Def", monster.baseStats.specialDefence],
      ["Speed", monster.baseStats.speed],
      ["Luck", monster.baseStats.luck],
      ["BST", monster.bst],
    ];

    statDefs.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "stat-row";
      const width = Math.max(4, Math.min(100, (Number(value) / 180) * 100));
      row.innerHTML = `
        <div class="label">${label}</div>
        <div class="value">${value}</div>
        <div class="bar"><div class="bar-fill" style="width:${width}%"></div></div>
      `;
      elements.stats.appendChild(row);
    });
  }

  function renderLearnset(monster) {
    elements.learnset.innerHTML = "";
    monster.learnset.forEach((entry) => {
      const move = entry.move || {};
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${entry.level}</td>
        <td>
          <span class="move-pill">
            ${move.type ? `<img src="${typeIconPath(move.type)}" alt="${move.type}" onerror="this.style.display='none'">` : ""}
            <span>${entry.moveName}</span>
          </span>
        </td>
        <td>${move.type || '<span class="muted">-</span>'}</td>
        <td>${move.category || '<span class="muted">-</span>'}</td>
        <td>${move.power || 0}</td>
        <td>${move.accuracy || 0}</td>
        <td>${move.manaCost || 0}</td>
        <td>${move.special || '<span class="muted">-</span>'}</td>
        <td>${move.description || '<span class="muted">No move data found.</span>'}</td>
      `;
      elements.learnset.appendChild(row);
    });
  }

  function clearFrame(frameElement) {
    frameElement.style.backgroundImage = "none";
    frameElement.style.backgroundPosition = "0 0";
    frameElement.style.backgroundSize = `${TILE_SIZE}px ${TILE_SIZE}px`;
    frameElement.dataset.state = "missing";
  }

  function drawDataSprite(frameElement, dataUrl) {
    if (!dataUrl) {
      clearFrame(frameElement);
      return;
    }
    frameElement.style.backgroundImage = `url("${dataUrl}")`;
    frameElement.style.backgroundSize = `${TILE_SIZE}px ${TILE_SIZE}px`;
    frameElement.style.backgroundPosition = "0 0";
    frameElement.dataset.state = "ready";
  }

  function renderDetail(monster) {
    state.selectedAbilityName = monster.abilities.some((ability) => ability.name === state.selectedAbilityName)
      ? state.selectedAbilityName
      : (monster.abilities[0] ? monster.abilities[0].name : null);
    elements.id.textContent = `#${String(monster.id).padStart(3, "0")}`;
    elements.name.textContent = monster.name;
    elements.identifier.textContent = monster.identifier;
    elements.description.textContent = monster.description;
    elements.types.innerHTML = "";
    monster.types.forEach((type) => elements.types.appendChild(createTypePill(type)));
    renderShape(monster);
    renderLore(monster);
    renderOverview(monster);
    renderAbilities(monster);
    renderStats(monster);
    renderLearnset(monster);
    drawDataSprite(elements.frontFrame, monster.frontSprite);
    drawDataSprite(elements.backFrame, monster.backSprite);
  }

  function getSelectedMonster() {
    return state.filtered.find((monster) => monster.slug === state.selectedSlug)
      || state.filtered[0]
      || data.monsters[0];
  }

  function applySearch() {
    const query = elements.search.value.trim().toLowerCase();
    state.filtered = data.monsters.filter((monster) => {
      if (!query) {
        return true;
      }
      const haystack = [
        monster.name,
        monster.identifier,
        monster.description,
        monster.types.join(" "),
        monster.abilities.map((ability) => ability.name).join(" "),
        monster.learnset.map((entry) => entry.moveName).join(" "),
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    });

    if (!state.filtered.some((monster) => monster.slug === state.selectedSlug)) {
      state.selectedSlug = state.filtered[0] ? state.filtered[0].slug : null;
    }
  }

  function render() {
    elements.count.textContent = `${state.filtered.length} of ${data.monsterCount} monsters`;
    renderList();

    const monster = getSelectedMonster();
    if (monster) {
      renderDetail(monster);
    }
  }

  elements.search.addEventListener("input", () => {
    applySearch();
    render();
  });

  applySearch();
  render();
})();
