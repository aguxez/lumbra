import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from config_loader import DAY_NIGHT, get_base_tier

SAVE_PATH = os.path.join(os.path.dirname(__file__), "savegame.json")


@dataclass
class ActiveBuff:
    source: str
    buff_type: str
    value: int
    ticks_remaining: int


@dataclass
class Expedition:
    destination: str
    description: str
    duration: int
    progress: int = 0
    status: str = "active"
    events: list[str] = field(default_factory=list)
    rewards: list[str] = field(default_factory=list)
    reward_xp: int = 0
    risk_level: int = 1

    @property
    def is_complete(self) -> bool:
        return self.progress >= self.duration

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "description": self.description,
            "duration": self.duration,
            "progress": self.progress,
            "status": self.status,
            "events": self.events[-3:],
            "rewards": self.rewards,
            "reward_xp": self.reward_xp,
            "risk_level": self.risk_level,
        }


@dataclass
class NPCEncounter:
    npc_name: str
    npc_role: str
    dialogue: str
    interaction_type: str
    offer_item: str | None = None
    request_item: str | None = None
    buff_type: str | None = None
    buff_value: int = 0
    buff_ticks: int = 0

    def to_dict(self) -> dict:
        return {
            "npc_name": self.npc_name,
            "npc_role": self.npc_role,
            "dialogue": self.dialogue,
            "interaction_type": self.interaction_type,
            "offer_item": self.offer_item,
            "request_item": self.request_item,
            "buff_type": self.buff_type,
            "buff_value": self.buff_value,
            "buff_ticks": self.buff_ticks,
        }


@dataclass
class InventoryItem:
    name: str
    rarity: str = "common"
    item_type: str = "accessory"
    attack: int = 0
    defense: int = 0
    effect_type: str | None = None
    effect_value: int = 0

    @classmethod
    def from_config(cls, data: dict, default_rarity: str = "common") -> "InventoryItem":
        return cls(
            name=data["name"],
            rarity=data.get("rarity", default_rarity),
            item_type=data.get("type", "accessory"),
            attack=data.get("attack", 0),
            defense=data.get("defense", 0),
            effect_type=data.get("effect", {}).get("type")
            if data.get("effect")
            else None,
            effect_value=data.get("effect", {}).get("value", 0)
            if data.get("effect")
            else 0,
        )


MAX_CONSUMABLE_PER_TYPE = 4


def _item_to_dict(item: InventoryItem) -> dict:
    return {
        "name": item.name,
        "rarity": item.rarity,
        "item_type": item.item_type,
        "attack": item.attack,
        "defense": item.defense,
        "effect_type": item.effect_type,
        "effect_value": item.effect_value,
    }


@dataclass
class Character:
    name: str = "Wanderer"
    hp: int = 50
    max_hp: int = 50
    attack: int = 8
    defense: int = 5
    xp: int = 0
    inventory: list[InventoryItem] = field(default_factory=list)
    equipped_weapon: InventoryItem | None = None
    equipped_armor: InventoryItem | None = None
    equipped_accessory: InventoryItem | None = None
    active_buffs: list[ActiveBuff] = field(default_factory=list)

    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def effective_attack(self) -> int:
        bonus = 0
        if self.equipped_weapon:
            bonus = self.equipped_weapon.attack
        buff_bonus = sum(b.value for b in self.active_buffs if b.buff_type == "attack")
        return max(0, self.attack + bonus + buff_bonus)

    @property
    def effective_defense(self) -> int:
        bonus = 0
        if self.equipped_armor:
            bonus = self.equipped_armor.defense
        if self.equipped_accessory:
            bonus += self.equipped_accessory.defense
        buff_bonus = sum(b.value for b in self.active_buffs if b.buff_type == "defense")
        return max(0, self.defense + bonus + buff_bonus)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "xp": self.xp,
            "equipment": {
                "weapon": _item_to_dict(self.equipped_weapon)
                if self.equipped_weapon
                else None,
                "armor": _item_to_dict(self.equipped_armor)
                if self.equipped_armor
                else None,
                "accessory": _item_to_dict(self.equipped_accessory)
                if self.equipped_accessory
                else None,
            },
            "inventory": [_item_to_dict(i) for i in self.inventory],
            "effective_attack": self.effective_attack,
            "effective_defense": self.effective_defense,
            "active_buffs": [
                {
                    "source": b.source,
                    "buff_type": b.buff_type,
                    "value": b.value,
                    "ticks_remaining": b.ticks_remaining,
                }
                for b in self.active_buffs
            ],
        }


@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int

    def is_alive(self) -> bool:
        return self.hp > 0

    def to_dict(self) -> dict:
        return {
            "enemy_name": self.name,
            "enemy_hp": self.hp,
            "enemy_max_hp": self.max_hp,
            "enemy_attack": self.attack,
            "enemy_defense": self.defense,
        }


@dataclass
class Quest:
    description: str
    target: str
    goal: int
    progress: int = 0
    reward_xp: int = 50
    reward_item: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.progress >= self.goal

    def to_dict(self) -> dict:
        d = {
            "description": self.description,
            "target": self.target,
            "goal": self.goal,
            "progress": self.progress,
            "reward_xp": self.reward_xp,
            "reward_item": self.reward_item,
        }
        return d


@dataclass
class Combat:
    enemy: Enemy
    turn: int = 1
    ai_strategy: str = "attack"

    def to_dict(self) -> dict:
        d = self.enemy.to_dict()
        d["turn"] = self.turn
        d["ai_strategy"] = self.ai_strategy
        return d


@dataclass
class Base:
    tier: int = 0
    name: str = "Campfire"
    storage: list[InventoryItem] = field(default_factory=list)


@dataclass
class GameState:
    tick: int = 0
    character: Character = field(default_factory=Character)
    zone: str = "Peaceful Meadow"
    quest: Quest | None = None
    combat: Combat | None = None
    npc_encounter: NPCEncounter | None = None
    npc_relationships: dict = field(default_factory=dict)
    expeditions: list[Expedition] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    base: Base = field(default_factory=Base)
    location: str = "exploring"
    ticks_exploring: int = 0
    was_night: bool = False

    @property
    def cycle_length(self) -> int:
        return max(1, DAY_NIGHT.get("cycle_length", 40))

    @property
    def night_start(self) -> int:
        return DAY_NIGHT.get("night_start", 25)

    @property
    def cycle_position(self) -> int:
        return self.tick % self.cycle_length

    @property
    def is_night(self) -> bool:
        return self.cycle_position >= self.night_start

    def to_dict(self) -> dict:
        base_tier_data = get_base_tier(self.base.tier)

        return {
            "tick": self.tick,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "character": self.character.to_dict(),
            "zone": self.zone,
            "quest": self.quest.to_dict() if self.quest else None,
            "combat": self.combat.to_dict() if self.combat else None,
            "npc_encounter": self.npc_encounter.to_dict()
            if self.npc_encounter
            else None,
            "expeditions": [
                e.to_dict() for e in self.expeditions if e.status == "active"
            ],
            "log": self.log[-10:],
            "base": {
                "tier": self.base.tier,
                "name": self.base.name,
                "storage": [_item_to_dict(i) for i in self.base.storage],
                "storage_slots": base_tier_data["storage_slots"]
                if base_tier_data
                else 0,
                "description": base_tier_data["description"] if base_tier_data else "",
            },
            "location": self.location,
            "is_night": self.is_night,
            "cycle_position": self.cycle_position,
            "cycle_length": self.cycle_length,
            "night_start": self.night_start,
        }

    def add_log(self, message: str):
        self.log.append(message)
        if len(self.log) > 50:
            self.log = self.log[-50:]

    def save(self, path: str = SAVE_PATH):
        char = self.character
        char_data = {
            "name": char.name,
            "hp": char.hp,
            "max_hp": char.max_hp,
            "attack": char.attack,
            "defense": char.defense,
            "xp": char.xp,
            "inventory": [asdict(i) for i in char.inventory],
            "equipped_weapon": asdict(char.equipped_weapon)
            if char.equipped_weapon
            else None,
            "equipped_armor": asdict(char.equipped_armor)
            if char.equipped_armor
            else None,
            "equipped_accessory": asdict(char.equipped_accessory)
            if char.equipped_accessory
            else None,
            "active_buffs": [asdict(b) for b in char.active_buffs],
        }
        data = {
            "tick": self.tick,
            "zone": self.zone,
            "character": char_data,
            "quest": asdict(self.quest) if self.quest else None,
            "combat": {
                "enemy": asdict(self.combat.enemy),
                "turn": self.combat.turn,
                "ai_strategy": self.combat.ai_strategy,
            }
            if self.combat
            else None,
            "npc_relationships": self.npc_relationships,
            "expeditions": [asdict(e) for e in self.expeditions],
            "log": self.log[-20:],
            "base": {
                "tier": self.base.tier,
                "name": self.base.name,
                "storage": [asdict(i) for i in self.base.storage],
            },
            "location": self.location,
            "ticks_exploring": self.ticks_exploring,
            "was_night": self.was_night,
        }
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str = SAVE_PATH) -> "GameState":
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return cls()

        char_data = data.get("character", {})

        def _load_item(d: dict | None) -> InventoryItem | None:
            if not d:
                return None
            return InventoryItem(
                name=d["name"],
                rarity=d.get("rarity", "common"),
                item_type=d.get("item_type", "accessory"),
                attack=d.get("attack", 0),
                defense=d.get("defense", 0),
                effect_type=d.get("effect_type"),
                effect_value=d.get("effect_value", 0),
            )

        raw_inventory = char_data.pop("inventory", [])
        inventory = [item for i in raw_inventory if i and (item := _load_item(i))]

        equipped_weapon = _load_item(char_data.pop("equipped_weapon", None))
        equipped_armor = _load_item(char_data.pop("equipped_armor", None))
        equipped_accessory = _load_item(char_data.pop("equipped_accessory", None))

        raw_buffs = char_data.pop("active_buffs", [])
        active_buffs = [
            ActiveBuff(
                source=b["source"],
                buff_type=b["buff_type"],
                value=b["value"],
                ticks_remaining=b["ticks_remaining"],
            )
            for b in raw_buffs
        ]

        # Remove any extra keys not in Character fields
        char_data.pop("effective_attack", None)
        char_data.pop("effective_defense", None)
        char_data.pop("weapon", None)
        char_data.pop("armor", None)
        char_data.pop("equipment", None)

        character = Character(
            **char_data,
            inventory=inventory,
            equipped_weapon=equipped_weapon,
            equipped_armor=equipped_armor,
            equipped_accessory=equipped_accessory,
            active_buffs=active_buffs,
        )

        quest = None
        if data.get("quest"):
            quest = Quest(**data["quest"])

        combat = None
        if data.get("combat"):
            enemy_data = data["combat"]["enemy"]
            enemy = Enemy(**enemy_data)
            combat = Combat(
                enemy=enemy,
                turn=data["combat"].get("turn", 1),
                ai_strategy=data["combat"].get("ai_strategy", "attack"),
            )

        expeditions = [
            Expedition(
                destination=e["destination"],
                description=e["description"],
                duration=e["duration"],
                progress=e.get("progress", 0),
                status=e.get("status", "active"),
                events=e.get("events", []),
                rewards=e.get("rewards", []),
                reward_xp=e.get("reward_xp", 0),
                risk_level=e.get("risk_level", 1),
            )
            for e in data.get("expeditions", [])
        ]

        # Load base state (backwards compatible — old saves get defaults)
        base_data = data.get("base", {})
        base = Base(
            tier=base_data.get("tier", 0),
            name=base_data.get("name", "Campfire"),
            storage=[
                item
                for i in base_data.get("storage", [])
                if i and (item := _load_item(i))
            ],
        )

        state = cls(
            tick=data.get("tick", 0),
            character=character,
            zone=data.get("zone", "Peaceful Meadow"),
            quest=quest,
            combat=combat,
            npc_relationships=data.get("npc_relationships", {}),
            expeditions=expeditions,
            log=data.get("log", []),
            base=base,
            location=data.get("location", "exploring"),
            ticks_exploring=data.get("ticks_exploring", 0),
            was_night=data.get("was_night", False),
        )
        return state
