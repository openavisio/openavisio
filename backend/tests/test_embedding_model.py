"""#238: which model embedded the corpus is recorded, so a model change is detectable."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.chat import DocumentChunk
from app.models.patient import Patient
from app.models.user import User


async def test_admin_ai_page_counts_chunks_per_embedding_model(client: AsyncClient, db: AsyncSession):
    admin = User(email="emb@t.com", hashed_password=hash_password("Pass1!"), role="admin", is_active=True,
                 first_name="T", last_name="Admin")
    db.add(admin)
    await db.flush()
    patient = Patient(given_name="Emma", family_name="Test", birth_date="2015-04-02", created_by=admin.id)
    db.add(patient)
    await db.flush()
    for i, model in enumerate(["old-embed", "old-embed", None, "new-embed"]):
        db.add(DocumentChunk(patient_id=patient.id, chunk_index=i, content="x", embedding_model=model,
                             is_deleted=model == "new-embed"))
    await db.commit()

    r = await client.post("/api/auth/login", json={"email": "emb@t.com", "password": "Pass1!"})
    r = await client.get("/api/admin/ollama", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert r.status_code == 200, r.text
    assert r.json()["corpus_embed_models"] == {"old-embed": 2, "": 1}
