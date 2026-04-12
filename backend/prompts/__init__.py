from enum import Enum


class PromptType(Enum):
    """
    Registry of all prompt types in the system.
    Add new prompt types here as the project grows.
    """
    DESCRIPTION = "description"
    TAXONOMY = "taxonomy"
    ASSIGNMENT = "assignment"
    RAG = "rag"
    ASK = "ask" 