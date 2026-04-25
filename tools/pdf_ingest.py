"""PDF ingestion pipeline: extract, OCR, vision, chunk, embed, store."""

import base64
import io
import logging
import os
import re

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from .base import Tool

logger = logging.getLogger("hive.tools.pdf_ingest")


class PDFIngestTool(Tool):
    def __init__(
        self,
        config: dict,
        database,
        embedding_service,
        ocr_tool,
        vision_agent,
        ollama_client,
        memory_config: dict,
        models_config: dict,
    ):
        super().__init__(config)
        self.database = database
        self.embedding_service = embedding_service
        self.ocr_tool = ocr_tool
        self.vision_agent = vision_agent
        self.ollama_client = ollama_client

        # Chunking settings
        self.chunk_size = memory_config.get("chunking", {}).get("chunk_size", 800)
        self.chunk_overlap = memory_config.get("chunking", {}).get("chunk_overlap", 100)

        # Pipeline toggles
        self.ocr_enabled = config.get("ocr_enabled", False) and self.ocr_tool is not None
        self.vision_enabled = config.get("vision_enabled", False) and self.vision_agent is not None
        self.render_dpi = config.get("render_dpi", 200)

        # Model for summaries
        self.chat_model = models_config.get("chat", {}).get("name", "llama3.1:8b")

    def get_name(self) -> str:
        return "pdf_ingest"

    def get_description(self) -> str:
        return "Process a PDF document: extract text, OCR images, describe visuals, chunk, embed, and store in memory."

    async def execute(self, params: dict) -> dict:
        if not self.enabled:
            return {"success": False, "error": "PDF ingest tool is disabled"}

        if not fitz:
            return {"success": False, "error": "PyMuPDF (fitz) is not installed"}

        file_path = params.get("file_path")
        project_id = params.get("project_id")
        title = params.get("title")

        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": f"PDF file not found: {file_path}"}

        if not title:
            title = os.path.basename(file_path)

        logger.info(f"Starting PDF ingestion: {title}")

        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            logger.info(f"Opened PDF: {total_pages} pages")

            # --- Stage 1: Extract text from all pages ---
            logger.info("Stage 1: Extracting text...")
            page_texts = self._extract_text(doc)

            # --- Stage 2: Render pages to images ---
            logger.info("Stage 2: Rendering pages to images...")
            page_images = self._render_pages(doc)

            doc.close()

            # --- Stage 3: OCR ---
            ocr_texts = {}
            if self.ocr_enabled:
                logger.info("Stage 3: Running OCR...")
                ocr_texts = await self._ocr_pages(page_images)
            else:
                logger.info("Stage 3: OCR disabled, skipping")

            # --- Stage 4: Vision descriptions ---
            vision_texts = {}
            if self.vision_enabled:
                logger.info("Stage 4: Running vision analysis...")
                vision_texts = await self._vision_pages(page_images)
            else:
                logger.info("Stage 4: Vision disabled, skipping")

            # --- Stage 5: Merge text per page ---
            logger.info("Stage 5: Merging text...")
            merged_texts = self._merge_texts(page_texts, ocr_texts, vision_texts, total_pages)

            # --- Stage 6: Chunk ---
            logger.info("Stage 6: Chunking text...")
            chunks = self._chunk_text(merged_texts)
            logger.info(f"Created {len(chunks)} chunks")

            # --- Stage 7 & 8: Store document and chunks with embeddings ---
            logger.info("Stage 7: Generating embeddings and storing...")
            doc_id = await self.database.store_document(
                title=title,
                file_path=file_path,
                doc_type="pdf",
                project_id=project_id,
            )

            chunks_stored = 0
            for i, chunk in enumerate(chunks):
                embedding = await self.embedding_service.embed_text(chunk["content"])
                blob = self.embedding_service.vector_to_bytes(embedding)
                await self.database.store_chunk(
                    document_id=doc_id,
                    chunk_index=i,
                    content=chunk["content"],
                    embedding=blob,
                )
                chunks_stored += 1
                if (i + 1) % 20 == 0:
                    logger.info(f"Embedded chunk {i + 1}/{len(chunks)}")

            # --- Stage 9: Generate bot summaries ---
            logger.info("Stage 8: Generating bot summaries...")
            memories_created = 0
            summary_interval = max(5, len(chunks) // 5)  # Every ~20% of chunks

            for start in range(0, len(chunks), summary_interval):
                batch = chunks[start : start + summary_interval]
                batch_text = "\n".join(c["content"] for c in batch)
                if len(batch_text.strip()) < 50:
                    continue

                summary = await self._generate_summary(batch_text, title)
                if summary:
                    emb = await self.embedding_service.embed_text(summary)
                    blob = self.embedding_service.vector_to_bytes(emb)
                    await self.database.store_memory(
                        content=summary,
                        category="summary",
                        importance=0.6,
                        project_id=project_id,
                        source_document_id=doc_id,
                        tags=[title],
                        embedding=blob,
                    )
                    memories_created += 1

            # --- Stage 10: Extract key concepts ---
            logger.info("Stage 9: Extracting key concepts...")
            full_text = "\n".join(
                c["content"] for c in chunks[:10]
            )  # Use first 10 chunks for concept extraction
            concepts = await self._extract_concepts(full_text, title)

            for concept in concepts:
                emb = await self.embedding_service.embed_text(concept)
                blob = self.embedding_service.vector_to_bytes(emb)
                await self.database.store_memory(
                    content=concept,
                    category="concept",
                    importance=0.5,
                    project_id=project_id,
                    source_document_id=doc_id,
                    tags=[title, "concept"],
                    embedding=blob,
                )
                memories_created += 1

            logger.info(
                f"PDF ingestion complete: {title} — "
                f"{total_pages} pages, {chunks_stored} chunks, {memories_created} memories"
            )

            return {
                "success": True,
                "result": {
                    "document_id": doc_id,
                    "pages_processed": total_pages,
                    "chunks_created": chunks_stored,
                    "memories_created": memories_created,
                },
            }

        except Exception as e:
            logger.error(f"PDF ingestion failed for {file_path}: {e}")
            return {"success": False, "error": str(e)}

    # ── Helpers ──────────────────────────────────────────────

    def _extract_text(self, doc) -> dict[int, str]:
        """Extract text from each page using PyMuPDF."""
        page_texts = {}
        for i, page in enumerate(doc):
            text = page.get_text("text")
            page_texts[i] = text if text else ""
        return page_texts

    def _render_pages(self, doc) -> dict[int, bytes]:
        """Render each page as a PNG image."""
        page_images = {}
        for i, page in enumerate(doc):
            try:
                pix = page.get_pixmap(dpi=self.render_dpi)
                page_images[i] = pix.tobytes("png")
            except Exception as e:
                logger.warning(f"Failed to render page {i}: {e}")
        return page_images

    async def _ocr_pages(self, page_images: dict[int, bytes]) -> dict[int, str]:
        """Run OCR on rendered page images."""
        ocr_texts = {}
        for page_num, img_bytes in page_images.items():
            try:
                result = await self.ocr_tool.execute({"image_bytes": img_bytes})
                if result.get("success"):
                    ocr_texts[page_num] = result.get("result", "")
            except Exception as e:
                logger.warning(f"OCR failed on page {page_num}: {e}")
        return ocr_texts

    async def _vision_pages(self, page_images: dict[int, bytes]) -> dict[int, str]:
        """Send page images to VisionAgent for descriptions."""
        vision_texts = {}
        for page_num, img_bytes in page_images.items():
            try:
                b64_img = base64.b64encode(img_bytes).decode("utf-8")
                messages = [
                    {
                        "role": "user",
                        "content": "Describe this document page. Focus on diagrams, charts, tables, layout, and visual elements.",
                    }
                ]
                result = await self.vision_agent.execute(
                    messages=messages, images=[b64_img]
                )
                content = result.get("content", "")
                if content:
                    vision_texts[page_num] = content
            except Exception as e:
                logger.warning(f"Vision analysis failed on page {page_num}: {e}")
        return vision_texts

    def _merge_texts(
        self,
        page_texts: dict[int, str],
        ocr_texts: dict[int, str],
        vision_texts: dict[int, str],
        total_pages: int,
    ) -> str:
        """Merge all text sources into a single document string."""
        parts = []
        for i in range(total_pages):
            page_parts = []

            # Primary extracted text
            text = page_texts.get(i, "").strip()
            if text:
                page_parts.append(text)

            # OCR text (deduplicated — only add lines not already in extracted text)
            ocr = ocr_texts.get(i, "").strip()
            if ocr and text:
                existing_lines = set(text.lower().split("\n"))
                new_lines = [
                    line
                    for line in ocr.split("\n")
                    if line.strip() and line.strip().lower() not in existing_lines
                ]
                if new_lines:
                    page_parts.append("[OCR]\n" + "\n".join(new_lines))
            elif ocr:
                page_parts.append("[OCR]\n" + ocr)

            # Vision descriptions
            vision = vision_texts.get(i, "").strip()
            if vision:
                page_parts.append("[Visual Description]\n" + vision)

            if page_parts:
                parts.append(f"--- Page {i + 1} ---\n" + "\n\n".join(page_parts))

        return "\n\n".join(parts)

    def _chunk_text(self, text: str) -> list[dict]:
        """Split text into overlapping chunks, respecting boundaries."""
        if not text.strip():
            return []

        words = text.split()
        if len(words) <= self.chunk_size:
            return [{"content": text.strip()}]

        chunks = []
        start = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            # Try to find a clean break point near the end
            if end < len(words):
                chunk_text = self._find_break_point(chunk_text)

            chunks.append({"content": chunk_text.strip()})

            # Advance with overlap
            step = self.chunk_size - self.chunk_overlap
            if step <= 0:
                step = max(1, self.chunk_size // 2)
            start += step

        return chunks

    def _find_break_point(self, text: str) -> str:
        """Try to break text at a natural boundary near the end."""
        # Look in the last 20% of the text for a break point
        search_start = int(len(text) * 0.8)
        search_region = text[search_start:]

        # Prefer paragraph break
        idx = search_region.rfind("\n\n")
        if idx != -1:
            return text[: search_start + idx]

        # Then newline
        idx = search_region.rfind("\n")
        if idx != -1:
            return text[: search_start + idx]

        # Then sentence ending
        for pattern in [". ", "? ", "! "]:
            idx = search_region.rfind(pattern)
            if idx != -1:
                return text[: search_start + idx + len(pattern)]

        # Give up, use full text
        return text

    async def _generate_summary(self, text: str, title: str) -> str:
        """Generate a bot-facing summary of a text section."""
        # Truncate input if very long to stay within model context
        if len(text) > 4000:
            text = text[:4000] + "..."

        try:
            response = await self.ollama_client.generate(
                model=self.chat_model,
                prompt=(
                    f"Summarize this section from '{title}' in 2-3 dense sentences. "
                    f"Write FOR A BOT that will read this later. Be factual, concise:\n\n{text}"
                ),
                temperature=0.3,
                max_tokens=256,
            )
            return response.strip() if response else ""
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            return ""

    async def _extract_concepts(self, text: str, title: str) -> list[str]:
        """Extract key concepts from the document."""
        if len(text) > 4000:
            text = text[:4000] + "..."

        try:
            response = await self.ollama_client.generate(
                model=self.chat_model,
                prompt=(
                    f"Extract 3-5 key concepts from this document '{title}'. "
                    f"Return each concept on its own line, no numbering, no bullets.\n\n{text}"
                ),
                temperature=0.3,
                max_tokens=256,
            )
            if not response:
                return []
            concepts = [
                line.strip() for line in response.strip().split("\n") if line.strip()
            ]
            return concepts[:5]
        except Exception as e:
            logger.warning(f"Concept extraction failed: {e}")
            return []
