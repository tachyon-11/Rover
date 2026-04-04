from pydantic import BaseModel, Field

class FolderCategory(BaseModel):
    category: str = Field(
        description="Top level folder name which would be defined based on broad topic that files within it relate to'"
    )
    subcategories: list[str] = Field(
        description="Subcategories within this category to drill down into more specific topics or types"
    )


class FolderTaxonomy(BaseModel):
    folders: list[FolderCategory] = Field(
        description="Complete folder structure for organizing all files"
    )

class FilePlan(BaseModel):
    file_id: str = Field(
        description="Exact UUID of the file fetched from the database, so we can update the record after moving"
    )
    new_path: str = Field(
        description="Full path e.g. Work/Resumes/Documents/Ujjwal_Resume_2024.pdf"
    )


class OrganizationPlan(BaseModel):
    files: list[FilePlan] = Field(
        description="Organization plan for each file in the batch"
    )