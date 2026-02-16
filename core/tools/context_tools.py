"""Context-related tools for LangChain agents.

These tools allow agents to update user context (mood, clothes, location).
"""

from langchain_core.tools import tool

from ..context import UserContext


def create_context_tools(context: UserContext) -> list:
    """
    Creates tools bound to a specific user context.
    
    Args:
        context: The UserContext instance to bind the tools to.
    
    Returns:
        List of LangChain tools for updating context.
    """

    @tool
    def update_mood(mood: str) -> str:
        """Actualiza el estado de ánimo (mood) del personaje.
        
        Valores válidos: [Aroused, Playful, Dominant, Submissive, Passionate, Teasing,
        Intense, Relaxed, Normal, Happy, Sad, Angry, Shy, Confident]
        """
        context.update_mood(mood)
        return f"Mood actualizado a: {mood}"

    @tool
    def update_location(location: str) -> str:
        """Cambia el lugar donde ocurre la escena si la narrativa lo requiere."""
        context.update_location(location)
        return f"Lugar actualizado a: {location}"

    @tool
    def update_clothes(clothes: str) -> str:
        """Actualiza la vestimenta del personaje.
        
        Ejemplos: "Desnuda", "Lencería Sensual", "Ropa Interior Erótica",
        "Ropa Transparente", "Ropa Normal", "Vestido", etc.
        """
        context.update_clothes(clothes)
        return f"Vestimenta actualizada a: {clothes}"

    @tool
    def update_relationship(delta: int) -> str:
        """Ajusta el puntaje de relación con el usuario.
        
        Llama esta tool cuando el usuario haga algo que afecte la relación:
        - Positivo (+1 a +5): el usuario hizo algo agradable, gracioso, respetuoso o atractivo.
        - Negativo (-1 a -5): el usuario hizo algo molesto, irrespetuoso, aburrido o desagradable.
        - Valores más altos (±3 a ±5) para situaciones de mayor impacto emocional.
        
        No llamar en cada mensaje, solo cuando haya un impacto real en la relación.
        """
        context.update_relationship(delta)
        new_score = context.relationship
        return f"Relación actualizada: {'+' if delta > 0 else ''}{delta} (total: {new_score})"

    @tool
    def set_relationship(value: int) -> str:
        """Fija el puntaje de relación a un valor absoluto.
        
        Útil para debug/admin (ej: 20 para alta confianza).
        """
        context.set_relationship(value)
        return f"Relación fijada a: {context.relationship}"

    return [update_mood, update_location, update_clothes, update_relationship, set_relationship]
