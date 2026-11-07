from pydantic import BaseModel
from typing import List


class AnalyzeRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SymbolInfo(BaseModel):
    kind: str
    name: str
    start_line: int
    end_line: int


class FileInfo(BaseModel):
    path: str
    language: str
    symbols: List[SymbolInfo]
    imports: List[str]


class StructureResponse(BaseModel):
    repo_id: int
    files: List[FileInfo]


class ImportantFile(BaseModel):
    path: str
    score: float
    rank: int


class ImportantFilesResponse(BaseModel):
    repo_id: int
    files: List[ImportantFile]


class SearchResult(BaseModel):
    file_path: str
    symbol_name: str
    kind: str
    start_line: int
    end_line: int
    score: float
    snippet: str


class SearchResponse(BaseModel):
    repo_id: int
    query: str
    results: List[SearchResult]


class AnalyzeResponse(BaseModel):
    repo_id: int
    url: str
    files_processed: int
    message: str
