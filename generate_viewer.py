#!/usr/bin/env python3
import base64
import csv
import json
import re
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIEWER_DIR = ROOT / "tools" / "Asobipedia"
MONSTERS_CSV = ROOT / "tools" / "CSVs" / "monsters.csv"
MOVES_CSV = ROOT / "tools" / "CSVs" / "moves.csv"
MONSTER_FILES_DIR = ROOT / "source" / "monsters"
ABILITIES_LUA = ROOT / "source" / "scripts" / "abilities.lua"
SHAPE_ICON_DIR = ROOT / "source" / "images" / "icons" / "menuIcons"
OUTPUT_JS = VIEWER_DIR / "data.js"

IMAGE_PATH_PATTERN = re.compile(r'imagePath\s*=\s*"([^"]+)"')
REGISTER_MONSTER_NAME_PATTERN = re.compile(r'REGISTER_MONSTER\("([^"]+)"')
TRIVIA_BLOCK_PATTERN = re.compile(r'trivia\s*=\s*\{(.*?)\}', re.DOTALL)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TILE_SIZE = 128
FRONT_TILE = (0, 1)
BACK_TILE = (0, 2)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def to_int(value, default=0):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def clean_ability_name(name: str) -> str:
    return name.replace(" (N)", "").strip()


def parse_abilities(raw: str):
    abilities = []
    for part in (raw or "").split(";"):
        entry = part.strip()
        if not entry:
            continue
        if ":" in entry:
            name, rate = entry.rsplit(":", 1)
            abilities.append({
                "name": clean_ability_name(name),
                "rate": to_int(rate, 0),
            })
        else:
            abilities.append({
                "name": clean_ability_name(entry),
                "rate": None,
            })
    return abilities


def parse_learnset(raw: str):
    learnset = []
    for part in (raw or "").split(";"):
        entry = part.strip()
        if not entry:
            continue
        match = re.match(r"(\d+)\s+(.+)", entry)
        if not match:
            continue
        level = int(match.group(1))
        move_name = match.group(2).strip()
        learnset.append({
            "level": level,
            "moveName": move_name,
        })
    return learnset


def read_png_rgba(path: Path):
    with path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise ValueError(f"{path} is not a PNG file")

        width = None
        height = None
        bit_depth = None
        color_type = None
        compressed = bytearray()

        while True:
            raw_length = handle.read(4)
            if not raw_length:
                break
            length = struct.unpack(">I", raw_length)[0]
            chunk_type = handle.read(4)
            chunk_data = handle.read(length)
            handle.read(4)

            if chunk_type == b"IHDR":
                width = struct.unpack(">I", chunk_data[0:4])[0]
                height = struct.unpack(">I", chunk_data[4:8])[0]
                bit_depth = chunk_data[8]
                color_type = chunk_data[9]
            elif chunk_type == b"IDAT":
                compressed.extend(chunk_data)
            elif chunk_type == b"IEND":
                break

    if bit_depth != 8 or color_type != 6:
        raise ValueError(f"Unsupported PNG format for {path}: bitDepth={bit_depth} colorType={color_type}")

    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    rows = []
    offset = 0
    previous = bytearray(stride)

    def paeth(a, b, c):
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride

        if filter_type == 1:
            for x in range(4, stride):
                row[x] = (row[x] + row[x - 4]) & 255
        elif filter_type == 2:
            for x in range(stride):
                row[x] = (row[x] + previous[x]) & 255
        elif filter_type == 3:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                up = previous[x]
                row[x] = (row[x] + ((left + up) >> 1)) & 255
        elif filter_type == 4:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                up = previous[x]
                up_left = previous[x - 4] if x >= 4 else 0
                row[x] = (row[x] + paeth(left, up, up_left)) & 255

        rows.append(row)
        previous = row

    return width, height, rows


def encode_png_rgba(width, height, rows):
    def chunk(chunk_type: bytes, data: bytes):
        crc = zlib.crc32(chunk_type)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw.extend(row)
    compressed = zlib.compress(bytes(raw), 9)
    png = bytearray(PNG_SIGNATURE)
    png.extend(chunk(b"IHDR", ihdr))
    png.extend(chunk(b"IDAT", compressed))
    png.extend(chunk(b"IEND", b""))
    return bytes(png)


def crop_tile_to_data_url(path: Path, tile_x: int, tile_y: int):
    width, height, rows = read_png_rgba(path)
    x0 = tile_x * TILE_SIZE
    y0 = tile_y * TILE_SIZE
    if x0 + TILE_SIZE > width or y0 + TILE_SIZE > height:
        return None

    cropped_rows = []
    start = x0 * 4
    end = (x0 + TILE_SIZE) * 4
    for y in range(y0, y0 + TILE_SIZE):
        cropped_rows.append(bytes(rows[y][start:end]))

    png_bytes = encode_png_rgba(TILE_SIZE, TILE_SIZE, cropped_rows)
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def load_image_paths():
    image_paths = {}
    for monster_file in MONSTER_FILES_DIR.glob("*.lua"):
        content = monster_file.read_text(encoding="utf-8")
        name_match = REGISTER_MONSTER_NAME_PATTERN.search(content)
        path_match = IMAGE_PATH_PATTERN.search(content)
        if not name_match or not path_match:
            continue
        image_paths[name_match.group(1)] = path_match.group(1)
    return image_paths


def load_shape_icons():
    shape_icons = {}
    for icon_file in SHAPE_ICON_DIR.glob("*MenuIcon.png"):
        stem = icon_file.stem
        if not stem.endswith("MenuIcon"):
            continue
        shape_name = stem[: -len("MenuIcon")]
        if not shape_name:
            continue
        key = shape_name[0].lower() + shape_name[1:]
        shape_icons[key] = "data:image/png;base64," + base64.b64encode(icon_file.read_bytes()).decode("ascii")
    return shape_icons


def normalize_lore_text(value):
    if value is None:
        return ""

    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized


def parse_monster_lore(content):
    behavior_match = re.search(r'behavior\s*=\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    habitat_match = re.search(r'habitat\s*=\s*"((?:[^"\\]|\\.)*)"', content, re.DOTALL)
    trivia_match = TRIVIA_BLOCK_PATTERN.search(content)

    behavior = normalize_lore_text(behavior_match.group(1)) if behavior_match else ""
    habitat = normalize_lore_text(habitat_match.group(1)) if habitat_match else ""

    trivia = []
    if trivia_match:
        trivia = []
        for entry in re.findall(r'"((?:[^"\\]|\\.)*)"', trivia_match.group(1), re.DOTALL):
            normalized_entry = normalize_lore_text(entry)
            if normalized_entry:
                trivia.append(normalized_entry)

    return {
        "behavior": behavior,
        "habitat": habitat,
        "trivia": trivia,
    }


def load_monster_lore():
    lore = {}
    for monster_file in MONSTER_FILES_DIR.glob("*.lua"):
        content = monster_file.read_text(encoding="utf-8")
        name_match = REGISTER_MONSTER_NAME_PATTERN.search(content)
        if not name_match:
            continue
        lore[name_match.group(1)] = parse_monster_lore(content)
    return lore


def load_moves():
    moves = {}
    with MOVES_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            move_name = (row.get("Name") or "").strip()
            if not move_name:
                continue
            moves[move_name] = {
                "className": (row.get("Class") or "").strip(),
                "name": move_name,
                "description": (row.get("Description") or "").strip(),
                "type": (row.get("Type") or "").strip(),
                "category": (row.get("Category") or "").strip(),
                "power": to_int(row.get("Power"), 0),
                "accuracy": to_int(row.get("Accuracy"), 0),
                "manaCost": to_int(row.get("ManaCost"), 0),
                "statusAdjust": (row.get("StatusAdjust") or "").strip(),
                "adjustAmount": to_int(row.get("AdjustAmount"), 0),
                "target": (row.get("Target") or "").strip(),
                "arenaChange": (row.get("ArenaChange") or "").strip(),
                "arenaDelay": to_int(row.get("ArenaDelay"), 0),
                "special": (row.get("Special") or "").strip(),
            }
    return moves


def load_ability_descriptions():
    text = ABILITIES_LUA.read_text(encoding="utf-8")
    pattern = re.compile(
        r'self\.name\s*=\s*"([^"]+)"\s*.*?self\.description\s*=\s*"([^"]+)"',
        re.DOTALL,
    )
    descriptions = {}
    for name, description in pattern.findall(text):
        descriptions[clean_ability_name(name)] = description.strip()
    return descriptions


def build_monsters(move_lookup, image_lookup, ability_descriptions, monster_lore, shape_icons):
    monsters = []
    with MONSTERS_CSV.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue

            base_stats = {
                "hp": to_int(row.get("Base HP")),
                "mana": to_int(row.get("Base Mana")),
                "attack": to_int(row.get("Base Attack")),
                "defence": to_int(row.get("Base Defence")),
                "specialAttack": to_int(row.get("Base Special Attack")),
                "specialDefence": to_int(row.get("Base Special Defence")),
                "speed": to_int(row.get("Base Speed")),
                "luck": to_int(row.get("Base Luck")),
            }
            bst = (
                base_stats["hp"]
                + base_stats["attack"]
                + base_stats["defence"]
                + base_stats["specialAttack"]
                + base_stats["specialDefence"]
                + base_stats["speed"]
            )

            types = [(row.get("Type") or "").strip()]
            secondary = (row.get("Secondary Type") or "").strip()
            if secondary:
                types.append(secondary)

            learnset = parse_learnset(row.get("Learnset"))
            for entry in learnset:
                move_data = move_lookup.get(entry["moveName"], {})
                entry["move"] = move_data

            image_path = image_lookup.get(name)
            image_sheet = f"../../source/{image_path}-table-128-128.png" if image_path else None
            front_sprite = None
            back_sprite = None
            if image_path:
                sprite_file = ROOT / "source" / f"{image_path}-table-128-128.png"
                if sprite_file.exists():
                    try:
                        front_sprite = crop_tile_to_data_url(sprite_file, BACK_TILE[0], BACK_TILE[1])
                        back_sprite = crop_tile_to_data_url(sprite_file, FRONT_TILE[0], FRONT_TILE[1])
                    except Exception:
                        front_sprite = None
                        back_sprite = None

            abilities = parse_abilities(row.get("Abilities"))
            for ability in abilities:
                ability["description"] = ability_descriptions.get(ability["name"], "")

            lore = monster_lore.get(name, {})

            monsters.append({
                "id": to_int(row.get("Card Number")),
                "slug": slugify(name),
                "name": name,
                "identifier": (row.get("Identifier") or "").strip(),
                "shape": (row.get("Shape") or "").strip(),
                "shapeIcon": shape_icons.get(((row.get("Shape") or "").strip()[:1].lower() + (row.get("Shape") or "").strip()[1:]), ""),
                "description": (row.get("Description") or "").strip(),
                "types": types,
                "height": (row.get("Height") or "").strip(),
                "weight": (row.get("Weight") or "").strip(),
                "levelingRate": (row.get("Leveling Rate") or "").strip(),
                "experienceYield": to_int(row.get("Experience Yield")),
                "catchRate": to_int(row.get("Catch Rate")),
                "maleChance": to_int(row.get("Male Chance")),
                "dvType": (row.get("DV Type") or "").strip(),
                "dvYield": to_int(row.get("DV Yield")),
                "tags": (row.get("Monster Tags") or "").strip(),
                "abilities": abilities,
                "baseStats": base_stats,
                "bst": bst,
                "learnset": learnset,
                "behavior": lore.get("behavior", ""),
                "habitat": lore.get("habitat", ""),
                "trivia": lore.get("trivia", []),
                "imageSheet": image_sheet,
                "frontSprite": front_sprite,
                "backSprite": back_sprite,
                "file": (row.get("File") or "").strip(),
            })

    monsters.sort(key=lambda monster: monster["id"])
    return monsters


def main():
    move_lookup = load_moves()
    image_lookup = load_image_paths()
    shape_icons = load_shape_icons()
    ability_descriptions = load_ability_descriptions()
    monster_lore = load_monster_lore()
    monsters = build_monsters(move_lookup, image_lookup, ability_descriptions, monster_lore, shape_icons)
    payload = {
        "generatedAt": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "monsterCount": len(monsters),
        "monsters": monsters,
    }

    OUTPUT_JS.write_text(
        "window.MONSTER_VIEWER_DATA = " + json.dumps(payload, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JS} with {len(monsters)} monsters.")


if __name__ == "__main__":
    main()
