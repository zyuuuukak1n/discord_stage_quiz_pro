# seed.py として保存
from src.database import SessionLocal, engine, Base
from src.models import Question, QuestionType

# テーブルを作成
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# テスト問題を追加
if db.query(Question).count() == 0:
    q1 = Question(question_type=QuestionType.descriptive, question_text="徳川家康が江戸幕府を開いたのは西暦何年？", sort_order=1)
    q2 = Question(question_type=QuestionType.descriptive, question_text="世界で一番面積の広い国はどこ？", sort_order=2)
    db.add_all([q1, q2])
    db.commit()
    print("テスト問題をDBに追加しました！")

db.close()
