import Foundation

struct GameStateResponse: Codable {
    let tick: Int
    let timestamp: String
    let character: CharacterState
    let zone: String
    let quest: QuestState?
    let combat: CombatState?
    let npc_encounter: NPCEncounterState?
    let expeditions: [ExpeditionState]?
    let log: [String]
}

struct CharacterState: Codable {
    let name: String
    let hp: Int
    let max_hp: Int
    let attack: Int
    let defense: Int
    let xp: Int
    let inventory: [InventoryItem]
    let weapon: String?
    let armor: String?
    let effective_attack: Int?
    let effective_defense: Int?
    let active_buffs: [ActiveBuffState]?
}

struct InventoryItem: Codable, Identifiable {
    var id: String { name }
    let name: String
    let rarity: String
    let item_type: String?
    let attack: Int?
    let defense: Int?
    let effect_type: String?
    let effect_value: Int?
}

struct QuestState: Codable {
    let description: String
    let target: String
    let goal: Int
    let progress: Int
    let reward_xp: Int
    let reward_item: String?
}

struct CombatState: Codable {
    let enemy_name: String
    let enemy_hp: Int
    let enemy_max_hp: Int
    let enemy_attack: Int
    let enemy_defense: Int
    let turn: Int
    let ai_strategy: String
}

struct ActiveBuffState: Codable {
    let source: String
    let buff_type: String
    let value: Int
    let ticks_remaining: Int
}

struct NPCEncounterState: Codable {
    let npc_name: String
    let npc_role: String
    let dialogue: String
    let interaction_type: String
    let offer_item: String?
    let request_item: String?
    let buff_type: String?
    let buff_value: Int?
    let buff_ticks: Int?
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
    let reward_xp: Int?
    let risk_level: Int?
}
