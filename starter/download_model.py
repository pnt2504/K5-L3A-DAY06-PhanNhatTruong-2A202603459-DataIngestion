from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "intfloat/multilingual-e5-small"
)

model.save("./models/multilingual-e5-small")

print("Đã tải model thành công!")