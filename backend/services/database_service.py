from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Tuple
from models.database import Article, Category, Tag, ChatMessage, User
from models.schemas import ArticleCreate, ArticleUpdate, CategoryCreate, TagCreate, UserCreate
import json


class DatabaseService:
    def __init__(self, db: Session):
        self.db = db
    
    # Статьи
    def get_articles(self, skip: int = 0, limit: int = 100, search: Optional[str] = None) -> Tuple[List[Article], int]:
        query = self.db.query(Article)
        
        if search:
            search_filter = or_(
                Article.title.ilike(f"%{search}%"),
                Article.text.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        total = query.count()
        articles = query.offset(skip).limit(limit).all()
        return articles, total
    
    def get_article(self, article_id: int) -> Optional[Article]:
        return self.db.query(Article).filter(Article.id == article_id).first()
    
    def create_article(self, article_data: ArticleCreate) -> Article:
        # Создаем статью
        article = Article(
            title=article_data.title,
            text=article_data.text,
            url=article_data.url,
            language=article_data.language
        )
        self.db.add(article)
        self.db.flush()  # Получаем ID
        
        # Добавляем категории
        if article_data.category_ids:
            categories = self.db.query(Category).filter(Category.id.in_(article_data.category_ids)).all()
            article.categories.extend(categories)
        
        # Добавляем теги
        if article_data.tag_names:
            for tag_name in article_data.tag_names:
                tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.db.add(tag)
                    self.db.flush()
                article.tags.append(tag)
        
        self.db.commit()
        self.db.refresh(article)
        return article
    
    def update_article(self, article_id: int, article_data: ArticleUpdate) -> Optional[Article]:
        article = self.get_article(article_id)
        if not article:
            return None
        
        # Обновляем поля
        if article_data.title is not None:
            article.title = article_data.title
        if article_data.text is not None:
            article.text = article_data.text
        if article_data.url is not None:
            article.url = article_data.url
        if article_data.language is not None:
            article.language = article_data.language
        
        # Обновляем категории
        if article_data.category_ids is not None:
            article.categories.clear()
            categories = self.db.query(Category).filter(Category.id.in_(article_data.category_ids)).all()
            article.categories.extend(categories)
        
        # Обновляем теги
        if article_data.tag_names is not None:
            article.tags.clear()
            for tag_name in article_data.tag_names:
                tag = self.db.query(Tag).filter(Tag.name == tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    self.db.add(tag)
                    self.db.flush()
                article.tags.append(tag)
        
        self.db.commit()
        self.db.refresh(article)
        return article
    
    def delete_article(self, article_id: int) -> bool:
        article = self.get_article(article_id)
        if not article:
            return False
        
        self.db.delete(article)
        self.db.commit()
        return True
    
    # Категории
    def get_categories(self) -> List[Category]:
        return self.db.query(Category).all()
    
    def get_category(self, category_id: int) -> Optional[Category]:
        return self.db.query(Category).filter(Category.id == category_id).first()
    
    def create_category(self, category_data: CategoryCreate) -> Category:
        category = Category(name=category_data.name, description=category_data.description)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category
    
    # Теги
    def get_tags(self) -> List[Tag]:
        return self.db.query(Tag).all()
    
    def get_tag(self, tag_id: int) -> Optional[Tag]:
        return self.db.query(Tag).filter(Tag.id == tag_id).first()
    
    def create_tag(self, tag_data: TagCreate) -> Tag:
        tag = Tag(name=tag_data.name)
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag
    
    # Поиск статей для RAG
    def search_articles_for_rag(self, query: str, limit: int = 5) -> List[Article]:
        # Простой поиск по заголовку и тексту
        search_filter = or_(
            Article.title.ilike(f"%{query}%"),
            Article.text.ilike(f"%{query}%")
        )
        return self.db.query(Article).filter(search_filter).limit(limit).all()

    def search_articles_by_meta(self, tokens: List[str], limit: int = 5) -> List[Article]:
        """
        Поиск статей по совпадению токенов с тегами/категориями.
        """
        if not tokens:
            return []
        toks = [t.upper() for t in tokens if t and len(t) >= 2]
        if not toks:
            return []
        # Теги
        tag_q = (
            self.db.query(Article)
            .join(Article.tags)
            .filter(Tag.name.in_(toks))
        )
        # Категории
        cat_q = (
            self.db.query(Article)
            .join(Article.categories)
            .filter(Category.name.in_(tokens))
        )
        # Объединяем и ограничиваем
        ids = {a.id for a in tag_q.limit(limit * 2).all()}
        for a in cat_q.limit(limit * 2).all():
            ids.add(a.id)
        if not ids:
            return []
        return (
            self.db.query(Article)
            .filter(Article.id.in_(list(ids)))
            .limit(limit)
            .all()
        )
    
    # Чат сообщения
    def save_chat_message(self, user_id: str, message: str, response: str, related_article_ids: List[int]) -> ChatMessage:
        chat_message = ChatMessage(
            user_id=user_id,
            message=message,
            response=response,
            related_article_ids=json.dumps(related_article_ids)
        )
        self.db.add(chat_message)
        self.db.commit()
        self.db.refresh(chat_message)
        return chat_message
    
    def update_feedback(self, message_id: int, feedback: int, comment: Optional[str] = None) -> bool:
        chat_message = self.db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
        if not chat_message:
            return False
        
        chat_message.feedback = feedback
        chat_message.feedback_comment = comment
        self.db.commit()
        return True

    # Пользователи
    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user_data: UserCreate, hashed_password: str, role: str = "user") -> User:
        user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_users(self) -> List[User]:
        return self.db.query(User).all()
