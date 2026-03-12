import Foundation

struct GameStateResponse: Codable {
  let tick: Int
  let timestamp: String
  let character: CharacterState
  let zone: String
  let quest: QuestState?
  let combat: CombatState?
  let npcEncounter: NPCEncounterState?
  let expeditions: [ExpeditionState]?
  let log: [String]

  enum CodingKeys: String, CodingKey {
    case tick, timestamp, character, zone, quest, combat, expeditions, log
    case npcEncounter = "npc_encounter"
  }
}

struct EquipmentState: Codable {
  let weapon: InventoryItem?
  let armor: InventoryItem?
  let accessory: InventoryItem?
}

struct CharacterState: Codable {
  let name: String
  let hitPoints: Int
  let maxHitPoints: Int
  let attack: Int
  let defense: Int
  let experience: Int
  let equipment: EquipmentState
  let inventory: [InventoryItem]
  let effectiveAttack: Int?
  let effectiveDefense: Int?
  let activeBuffs: [ActiveBuffState]?

  enum CodingKeys: String, CodingKey {
    case name, attack, defense, equipment, inventory
    case hitPoints = "hp"
    case maxHitPoints = "max_hp"
    case experience = "xp"
    case effectiveAttack = "effective_attack"
    case effectiveDefense = "effective_defense"
    case activeBuffs = "active_buffs"
  }
}

struct InventoryItem: Codable, Identifiable {
  var id: String { name }
  let name: String
  let rarity: String
  let itemType: String?
  let attack: Int?
  let defense: Int?
  let effectType: String?
  let effectValue: Int?

  enum CodingKeys: String, CodingKey {
    case name, rarity, attack, defense
    case itemType = "item_type"
    case effectType = "effect_type"
    case effectValue = "effect_value"
  }
}

struct QuestState: Codable {
  let description: String
  let target: String
  let goal: Int
  let progress: Int
  let rewardXp: Int
  let rewardItem: String?

  enum CodingKeys: String, CodingKey {
    case description, target, goal, progress
    case rewardXp = "reward_xp"
    case rewardItem = "reward_item"
  }
}

struct CombatState: Codable {
  let enemyName: String
  let enemyHp: Int
  let enemyMaxHp: Int
  let enemyAttack: Int
  let enemyDefense: Int
  let turn: Int
  let aiStrategy: String

  enum CodingKeys: String, CodingKey {
    case turn
    case enemyName = "enemy_name"
    case enemyHp = "enemy_hp"
    case enemyMaxHp = "enemy_max_hp"
    case enemyAttack = "enemy_attack"
    case enemyDefense = "enemy_defense"
    case aiStrategy = "ai_strategy"
  }
}

struct ActiveBuffState: Codable {
  let source: String
  let buffType: String
  let value: Int
  let ticksRemaining: Int

  enum CodingKeys: String, CodingKey {
    case source, value
    case buffType = "buff_type"
    case ticksRemaining = "ticks_remaining"
  }
}

struct NPCEncounterState: Codable {
  let npcName: String
  let npcRole: String
  let dialogue: String
  let interactionType: String
  let offerItem: String?
  let requestItem: String?
  let buffType: String?
  let buffValue: Int?
  let buffTicks: Int?

  enum CodingKeys: String, CodingKey {
    case dialogue
    case npcName = "npc_name"
    case npcRole = "npc_role"
    case interactionType = "interaction_type"
    case offerItem = "offer_item"
    case requestItem = "request_item"
    case buffType = "buff_type"
    case buffValue = "buff_value"
    case buffTicks = "buff_ticks"
  }
}

struct ExpeditionState: Codable, Identifiable {
  var id: String { destination + "_" + String(duration) }
  let destination: String
  let description: String
  let duration: Int
  let progress: Int
  let status: String
  let events: [String]?
  let rewards: [String]?
  let rewardXp: Int?
  let riskLevel: Int?

  enum CodingKeys: String, CodingKey {
    case destination, description, duration, progress, status, events, rewards
    case rewardXp = "reward_xp"
    case riskLevel = "risk_level"
  }
}
