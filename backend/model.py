from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """用户表"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    preferences = db.Column(db.String(200))  # JSON格式存储偏好
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    bookings = db.relationship('Booking', backref='user', lazy=True)

class Seat(db.Model):
    """座位表"""
    id = db.Column(db.Integer, primary_key=True)
    seat_number = db.Column(db.String(20), unique=True, nullable=False)
    floor = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(20))  # A区、B区等
    has_power = db.Column(db.Boolean, default=False)  # 是否有插座
    near_window = db.Column(db.Boolean, default=False)  # 是否靠窗
    status = db.Column(db.String(20), default='available')  # available, occupied, maintenance
    
    bookings = db.relationship('Booking', backref='seat', lazy=True)

class Booking(db.Model):
    """预约表"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    check_in = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Integer)  # 1-5星评分
    created_at = db.Column(db.DateTime, default=datetime.now)
