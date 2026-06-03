import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        """MongoDB Atlas bilan ulanish"""
        mongodb_uri = os.getenv('MONGODB_URI')
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable topilmadi!")
        
        try:
            self.client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
            # Ulanishni tekshirish
            self.client.admin.command('ping')
            self.db = self.client['manhwa_bot']
            
            # Collections (jadval)
            self.manhwas = self.db['manhwas']  # Manhwa fayllari
            self.users = self.db['users']      # Foydalanuvchilar
            self.stats = self.db['stats']      # Statistika
            
            # Index yaratish
            self.manhwas.create_index('title')
            self.manhwas.create_index('genre')
            self.manhwas.create_index('chapter')
            self.manhwas.create_index('file_id', unique=True)
            self.users.create_index('user_id', unique=True)
            
            logger.info("✅ MongoDB Atlas bilan ulanish muvaffaqiyatli!")
            
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB ulanishda xato: {e}")
            raise
    
    # ============ Manhwa CRUD operatsiyalari ============
    
    def add_manhwa(self, file_id, title, chapter, genre=None, description=None, 
                   uploaded_by=None, file_name=None, file_size=None, media_type='document'):
        """Yangi manhwa qo'shish"""
        manhwa = {
            'file_id': file_id,
            'title': title,
            'chapter': chapter,
            'genre': genre or [],
            'description': description,
            'uploaded_by': uploaded_by,
            'file_name': file_name,
            'file_size': file_size,
            'media_type': media_type,  # document, photo, video
            'downloads': 0,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        try:
            result = self.manhwas.insert_one(manhwa)
            logger.info(f"Yangi manhwa qo'shildi: {title} - Chapter {chapter}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Manhwa qo'shishda xato: {e}")
            return None
    
    def get_manhwa_by_file_id(self, file_id):
        """File ID bo'yicha manhwa topish"""
        return self.manhwas.find_one({'file_id': file_id})
    
    def search_manhwa(self, query, limit=20):
        """Manhwa qidirish (nomi, janri bo'yicha)"""
        # Text search yoki regex bilan qidirish
        regex_query = {'$regex': query, '$options': 'i'}
        
        results = self.manhwas.find({
            '$or': [
                {'title': regex_query},
                {'description': regex_query},
                {'genre': regex_query}
            ]
        }).sort('created_at', -1).limit(limit)
        
        return list(results)
    
    def get_all_manhwas(self, page=1, per_page=10):
        """Barcha manhwalarni olish (paginatsiya bilan)"""
        skip = (page - 1) * per_page
        manhwas = self.manhwas.find().sort('created_at', -1).skip(skip).limit(per_page)
        total = self.manhwas.count_documents({})
        
        return {
            'manhwas': list(manhwas),
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': -(-total // per_page)  # Ceiling division
        }
    
    def get_manhwas_by_genre(self, genre, page=1, per_page=10):
        """Janr bo'yicha manhwalar"""
        skip = (page - 1) * per_page
        manhwas = self.manhwas.find({'genre': genre}).sort('created_at', -1).skip(skip).limit(per_page)
        total = self.manhwas.count_documents({'genre': genre})
        
        return {
            'manhwas': list(manhwas),
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': -(-total // per_page)
        }
    
    def delete_manhwa(self, file_id):
        """Manhwa o'chirish"""
        result = self.manhwas.delete_one({'file_id': file_id})
        return result.deleted_count > 0
    
    def increment_downloads(self, file_id):
        """Yuklab olishlar sonini oshirish"""
        self.manhwas.update_one(
            {'file_id': file_id},
            {'$inc': {'downloads': 1}, '$set': {'updated_at': datetime.utcnow()}}
        )
    
    def get_all_genres(self):
        """Barcha janrlarni olish"""
        return self.manhwas.distinct('genre')
    
    def get_stats(self):
        """Statistika"""
        return {
            'total_manhwas': self.manhwas.count_documents({}),
            'total_users': self.users.count_documents({}),
            'total_downloads': sum(m.get('downloads', 0) for m in self.manhwas.find({}, {'downloads': 1}))
        }
    
    # ============ User operatsiyalari ============
    
    def add_or_update_user(self, user_id, username=None, first_name=None, last_name=None):
        """Foydalanuvchini qo'shish yoki yangilash"""
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'last_active': datetime.utcnow()
        }
        
        self.users.update_one(
            {'user_id': user_id},
            {'$set': user_data},
            upsert=True
        )
    
    def get_all_users(self):
        """Barcha foydalanuvchilar"""
        return list(self.users.find())
    
    # ============ Statistika ============
    
    def log_download(self, user_id, manhwa_title, chapter):
        """Yuklab olish statistikasi"""
        self.stats.insert_one({
            'user_id': user_id,
            'manhwa_title': manhwa_title,
            'chapter': chapter,
            'timestamp': datetime.utcnow()
        })

# Global database obyekti
db = Database()
