from typing import Optional, Dict, List
from pydantic import BaseModel, Field

# Definimos el contexto usando Pydantic para validación y facilidad de uso con LangChain
class UserContext(BaseModel):
    user_id: int
    # Identidad del personaje
    char_key: str = ""  # Clave interna del personaje (ej: "sofia")
    char_name: str = ""  # Nombre del personaje
    personality: str = ""  # Descripción completa de personalidad
    likes: List[str] = []  # Gustos del personaje
    dislikes: List[str] = []  # Lo que no le gusta
    physical_description: str = ""  # Tags de apariencia para imágenes
    outfits: Dict[str, str] = {}  # Todos los atuendos disponibles (key -> tags)
    home: Dict[str, dict] = {}  # Descripción del hogar del personaje (bedroom, livingroom, etc.)
    
    # Estado actual del roleplay
    character: str = ""  # "Nombre — Personalidad" (legacy, usado por el system prompt)
    scenario: str = ""  # Nombre del escenario activo
    scenario_context: str = ""  # Texto narrativo del escenario inicial
    initial_action: str = ""  # Acción inicial del personaje
    clothes: str = ""  # Tags de ropa actual
    clothes_key: str = ""  # Clave del outfit actual (ej: "partywear")
    location: str = ""  # Clave de ubicación actual (ej: "nightclub")
    mood: str = "Normal"
    
    # Mundo
    world_type: str = ""  # realistic, medieval_fantasy, sci_fi
    world_rules: str = ""  # Reglas del mundo en texto para el agente
    
    # Relación
    relationship: int = 0  # Puntaje de relación: 0=neutral, positivo=confianza, negativo=rechazo

    # Sesión
    msg_count: int = 0
    is_setup_complete: bool = False
    energy: int = 100

    def has_energy(self, amount: int) -> bool:
        return self.energy >= amount

    def consume_energy(self, amount: int):
        self.energy = max(0, self.energy - amount)

    def add_energy(self, amount: int):
        self.energy += amount

    def update_mood(self, new_mood: str):
        self.mood = new_mood

    def update_character(self, new_character: str):
        self.character = new_character

    def update_scenario(self, new_scenario: str):
        self.scenario = new_scenario

    def update_location(self, new_location: str):
        self.location = new_location

    def update_clothes(self, new_clothes: str):
        self.clothes = new_clothes

    def update_relationship(self, delta: int):
        self.relationship += delta

class ContextManager:
    def __init__(self):
        self._contexts: Dict[int, UserContext] = {}

    def get_context(self, user_id: int) -> UserContext:
        if user_id not in self._contexts:
            self._contexts[user_id] = UserContext(user_id=user_id)
        return self._contexts[user_id]

    def reset_context(self, user_id: int):
        if user_id in self._contexts:
            del self._contexts[user_id]
        return self.get_context(user_id)
