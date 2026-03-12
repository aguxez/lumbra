import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

SAVE_PATH = os.path.join(os.path.dirname(__file__), "savegame.json")


@dataclass
class InventoryItem:
    name: str
    rarity: str = "common"
    item_type: str = "accessory"
    attack: int = 0
    defense: int = 0
    effect_type: Optional[str] = None
    effect_value: int = 0


@dataclass
class Character:
    name: str = "Wanderer"
    hp: int = 50
    max_hp: int = 50
    attack: int = 8
    defense: int = 5
    xp: int = 0
    inventory: list[InventoryItem] = field(default_factory=list)
    weapon: Optional[str] = None
    armor: Optional[str] = None

    def is_alive(self) -> bool:
        return self.hp > 0

    @property
    def effective_attack(self) -> int:
        bonus = 0
        if self.weapon:
            item = next((i for i in self.inventory if i.name == self.weapon), None)
            if item:
                bonus = item.attack
        return self.attack + bonus

    @property
    def effective_defense(self) -> int:
        bonus = 0
        if self.armor:
            item = next((i for i in self.inventory if i.name == self.armor), None)
            if item:
                bonus = item.defense
        return self.defense + bonus

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "xp": self.xp,
            "inventory": [
                {
                    "name": i.name,
                    "rarity": i.rarity,
                    "item_type": i.item_type,
                    "attack": i.attack,
                    "defense": i.defense,
                    "effect_type": i.effect_type,
                    "effect_value": i.effect_value,
                }
                for i in self.inventory
            ],
            "weapon": self.weapon,
            "armor": self.armor,
            "effective_attack": self.effective_attack,
            "effective_defense": self.effective_defense,
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
    reward_item: Optional[str] = None

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
class GameState:
    tick: int = 0
    character: Character = field(default_factory=Character)
    zone: str = "Peaceful Meadow"
    quest: Optional[Quest] = None
    combat: Optional[Combat] = None
    log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "character": self.character.to_dict(),
            "zone": self.zone,
            "quest": self.quest.to_dict() if self.quest else None,
            "combat": self.combat.to_dict() if self.combat else None,
            "log": self.log[-10:],
        }

    def add_log(self, message: str):
        self.log.append(message)
        if len(self.log) > 50:
            self.log = self.log[-50:]

    def save(self, path: str = SAVE_PATH):
        data = {
            "tick": self.tick,
            "zone": self.zone,
            "character": asdict(self.character),
            "quest": asdict(self.quest) if self.quest else None,
            "combat": {
                "enemy": asdict(self.combat.enemy),
                "turn": self.combat.turn,
                "ai_strategy": self.combat.ai_strategy,
            }
            if self.combat
            else None,
            "log": self.log[-20:],
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
        raw_inventory = char_data.pop("inventory", [])
        inventory = [
            InventoryItem(
                name=i["name"],
                rarity=i.get("rarity", "common"),
                item_type=i.get("item_type", "accessory"),
                attack=i.get("attack", 0),
                defense=i.get("defense", 0),
                effect_type=i.get("effect_type"),
                effect_value=i.get("effect_value", 0),
            )
            for i in raw_inventory
        ]
        # Remove computed properties before constructing
        char_data.pop("effective_attack", None)
        char_data.pop("effective_defense", None)
        weapon = char_data.pop("weapon", None)
        armor = char_data.pop("armor", None)
        character = Character(
            **char_data, inventory=inventory, weapon=weapon, armor=armor
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

        state = cls(
            tick=data.get("tick", 0),
            character=character,
            zone=data.get("zone", "Peaceful Meadow"),
            quest=quest,
            combat=combat,
            log=data.get("log", []),
        )
        return state
