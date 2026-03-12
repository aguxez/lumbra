import Foundation

struct GameStateResponse: Codable {
    let tick: Int
    let timestamp: String
    let character: CharacterState
    let zone: String
    let quest: QuestState?
    let combat: CombatState?
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
