import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from models import User, Seat, Booking, db

class CollaborativeRecommender:
    """协同过滤推荐系统"""
    
    def __init__(self):
        self.user_seat_matrix = None
        self.similarity_matrix = None
    
    def build_matrix(self):
        """构建用户-座位评分矩阵"""
        users = User.query.all()
        seats = Seat.query.all()
        
        # 创建空矩阵
        matrix = np.zeros((len(users), len(seats)))
        
        # 填充评分数据
        for booking in Booking.query.filter_by(status='completed').all():
            user_idx = booking.user_id - 1
            seat_idx = booking.seat_id - 1
            
            # 评分 = 实际评分 或 根据使用时长计算
            if booking.rating:
                score = booking.rating
            else:
                # 使用时长转换为评分
                duration = (booking.end_time - booking.start_time).seconds / 3600
                score = min(5, max(1, duration / 2 + 2))
            
            matrix[user_idx][seat_idx] = score
        
        self.user_seat_matrix = matrix
        return matrix
    
    def calculate_similarity(self):
        """计算用户相似度"""
        if self.user_seat_matrix is None:
            self.build_matrix()
        
        # 使用余弦相似度
        self.similarity_matrix = cosine_similarity(self.user_seat_matrix)
        return self.similarity_matrix
    
    def recommend(self, user_id, n=5, filters=None):
        """为用户推荐座位"""
        if self.similarity_matrix is None:
            self.calculate_similarity()
        
        user_idx = user_id - 1
        
        # 获取相似用户
        similar_users = self.similarity_matrix[user_idx]
        
        # 预测评分
        predicted_scores = {}
        seats = Seat.query.all()
        
        for seat_idx, seat in enumerate(seats):
            # 跳过已使用过的座位
            if self.user_seat_matrix[user_idx][seat_idx] > 0:
                continue
            
            # 应用过滤条件
            if filters:
                if filters.get('has_power') and not seat.has_power:
                    continue
                if filters.get('near_window') and not seat.near_window:
                    continue
                if filters.get('floor') and seat.floor != filters['floor']:
                    continue
            
            # 计算预测评分
            numerator = 0
            denominator = 0
            
            for other_user_idx, similarity in enumerate(similar_users):
                if other_user_idx == user_idx:
                    continue
                
                rating = self.user_seat_matrix[other_user_idx][seat_idx]
                if rating > 0:
                    numerator += similarity * rating
                    denominator += abs(similarity)
            
            if denominator > 0:
                predicted_scores[seat.id] = numerator / denominator
            else:
                # 默认分数
                predicted_scores[seat.id] = 3.0
        
        # 排序并返回top-n
        sorted_seats = sorted(predicted_scores.items(), 
                             key=lambda x: x[1], 
                             reverse=True)[:n]
        
        return [{'seat_id': seat_id, 'score': score} 
                for seat_id, score in sorted_seats]
