# matching/rag_matcher.py
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from models import Mission, MissionRecommandee, Signal
from matching.llm_matcher import match_with_llm


class RAGMatcher:

    def __init__(self, catalogue: list[Mission]):
        self.index = {m.id: m for m in catalogue}
        self.vectorstore = self._build_index(catalogue)

    def _build_index(self, catalogue: list[Mission]) -> Chroma:
        docs = [
            Document(
                page_content=f"{m.titre}. {m.description}. {m.benefice_client}",
                metadata={"mission_id": m.id},
            )
            for m in catalogue
        ]
        return Chroma.from_documents(
            documents=docs,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        )

    def retrieve_candidates(self, signaux: list[Signal], k: int = 3) -> list[Mission]:
        seen, candidates = set(), []
        for signal in signaux:
            query = f"{signal.titre}. {signal.description}. {signal.levier}"
            for doc in self.vectorstore.similarity_search(query, k=k):
                mid = doc.metadata["mission_id"]
                if mid not in seen:
                    seen.add(mid)
                    candidates.append(self.index[mid])
        return candidates

    def match(self, signaux: list[Signal], llm: ChatOpenAI) -> list[MissionRecommandee]:
        candidates = self.retrieve_candidates(signaux)
        return match_with_llm(signaux, candidates, llm)
