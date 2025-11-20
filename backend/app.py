from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, User, Seat, Booking
from algorithms.recommender import CollaborativeRecommender
from algorithms.optimizer import GeneticAlgorithmOptimizer
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)

db.init_app(app)

# 初始化推荐器
recommender = CollaborativeRecommender()
optimizer = GeneticAlgorithmOptimizer()

# ============ 用户管理 ============

@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.json
    
    # 检查用户名是否存在
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': '用户名已存在'}), 400
    
    user = User(
        username=data['username'],
        password=data['password'],  # 实际应该加密
        email=data.get('email', ''),
        preferences=json.dumps(data.get('preferences', {}))
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': '注册成功', 'user_id': user.id})

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    user = User.query.filter_by(
        username=data['username'],
        password=data['password']
    ).first()
    
    if user:
        return jsonify({
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        })
    else:
        return jsonify({'error': '用户名或密码错误'}), 401

# ============ 座位管理 ============

@app.route('/api/seats', methods=['GET'])
def get_seats():
    """获取所有座位"""
    floor = request.args.get('floor', type=int)
    area = request.args.get('area')
    
    query = Seat.query
    
    if floor:
        query = query.filter_by(floor=floor)
    if area:
        query = query.filter_by(area=area)
    
    seats = query.all()
    
    return jsonify([{
        'id': s.id,
        'seat_number': s.seat_number,
        'floor': s.floor,
        'area': s.area,
        'has_power': s.has_power,
        'near_window': s.near_window,
        'status': s.status
    } for s in seats])

@app.route('/api/seats/<int:seat_id>/availability', methods=['GET'])
def check_availability(seat_id):
    """检查座位可用性"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # 查询当天的预约
    start = datetime.strptime(date, '%Y-%m-%d')
    end = start + timedelta(days=1)
    
    bookings = Booking.query.filter(
        Booking.seat_id == seat_id,
        Booking.start_time >= start,
        Booking.start_time < end,
        Booking.status == 'active'
    ).all()
    
    occupied_slots = [{
        'start': b.start_time.strftime('%H:%M'),
        'end': b.end_time.strftime('%H:%M')
    } for b in bookings]
    
    return jsonify({'occupied_slots': occupied_slots})

# ============ 推荐系统 ============

@app.route('/api/recommend', methods=['POST'])
def recommend_seats():
    """推荐座位"""
    data = request.json
    user_id = data['user_id']
    filters = data.get('filters', {})
    n = data.get('n', 5)
    
    # 获取推荐
    recommendations = recommender.recommend(user_id, n=n, filters=filters)
    
    # 补充座位详情
    result = []
    for rec in recommendations:
        seat = Seat.query.get(rec['seat_id'])
        result.append({
            'seat_id': seat.id,
            'seat_number': seat.seat_number,
            'floor': seat.floor,
            'area': seat.area,
            'has_power': seat.has_power,
            'near_window': seat.near_window,
            'score': round(rec['score'], 2),
            'reason': '基于您的历史偏好推荐'
        })
    
    return jsonify(result)

# ============ 预约管理 ============

@app.route('/api/bookings', methods=['POST'])
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    """创建预约"""
    data = request.json

    print("收到预约请求:", data)  # 调试信息

    # 解析时间（兼容多种格式）
    try:
        start_str = data['start_time'].replace('Z', '').replace('+00:00', '')[:19]
        end_str = data['end_time'].replace('Z', '').replace('+00:00', '')[:19]
        start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
        end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
    except Exception as e:
        print("时间解析错误:", e)
        return jsonify({'error': '时间格式错误'}), 400

    # 检查时间冲突
    conflicts = Booking.query.filter(
        Booking.seat_id == data['seat_id'],
        Booking.start_time < end_time,
        Booking.end_time > start_time,
        Booking.status == 'active'
    ).first()

    if conflicts:
        return jsonify({'error': '该时间段已被预约'}), 400

    # 创建预约
    booking = Booking(
        user_id=data['user_id'],
        seat_id=data['seat_id'],
        start_time=start_time,
        end_time=end_time
    )

    db.session.add(booking)
    db.session.commit()

    print(f"预约成功: 用户{data['user_id']} 座位{data['seat_id']}")  # 调试信息

    return jsonify({
        'message': '预约成功',
        'booking_id': booking.id
    })

@app.route('/api/bookings/<int:user_id>', methods=['GET'])
def get_user_bookings(user_id):
    """获取用户预约"""
    bookings = Booking.query.filter_by(user_id=user_id).order_by(
        Booking.start_time.desc()
    ).all()
    
    result = []
    for b in bookings:
        seat = Seat.query.get(b.seat_id)
        result.append({
            'id': b.id,
            'seat_number': seat.seat_number,
            'floor': seat.floor,
            'area': seat.area,
            'start_time': b.start_time.strftime('%Y-%m-%d %H:%M'),
            'end_time': b.end_time.strftime('%Y-%m-%d %H:%M'),
            'status': b.status,
            'check_in': b.check_in
        })
    
    return jsonify(result)

@app.route('/api/bookings/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """取消预约"""
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': '预约不存在'}), 404
    
    booking.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'message': '预约已取消'})

@app.route('/api/bookings/<int:booking_id>/checkin', methods=['POST'])
def checkin(booking_id):
    """签到"""
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': '预约不存在'}), 404
    
    booking.check_in = True
    db.session.commit()
    
    return jsonify({'message': '签到成功'})

@app.route('/api/bookings/<int:booking_id>/rate', methods=['POST'])
def rate_booking(booking_id):
    """评价座位"""
    data = request.json
    booking = Booking.query.get(booking_id)
    
    if not booking:
        return jsonify({'error': '预约不存在'}), 404
    
    booking.rating = data['rating']
    booking.status = 'completed'
    db.session.commit()
    
    # 重新训练推荐模型
    recommender.build_matrix()
    recommender.calculate_similarity()
    
    return jsonify({'message': '评价成功'})

# ============ 数据分析 ============

@app.route('/api/analytics/occupancy', methods=['GET'])
def get_occupancy_stats():
    """获取占用率统计"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    start = datetime.strptime(date, '%Y-%m-%d')
    end = start + timedelta(days=1)
    
    # 按小时统计
    hourly_stats = []
    total_seats = Seat.query.count()
    
    for hour in range(8, 22):  # 8:00 - 22:00
        time_start = start.replace(hour=hour)
        time_end = time_start + timedelta(hours=1)
        
        occupied = Booking.query.filter(
            Booking.start_time < time_end,
            Booking.end_time > time_start,
            Booking.status == 'active'
        ).count()
        
        hourly_stats.append({
            'hour': f'{hour:02d}:00',
            'occupancy': occupied,
            'rate': round(occupied / total_seats * 100, 2)
        })
    
    return jsonify(hourly_stats)

@app.route('/api/analytics/popular-seats', methods=['GET'])
def get_popular_seats():
    """获取热门座位"""
    from sqlalchemy import func
    
    popular = db.session.query(
        Seat.seat_number,
        Seat.floor,
        Seat.area,
        func.count(Booking.id).label('count')
    ).join(Booking).group_by(Seat.id).order_by(
        func.count(Booking.id).desc()
    ).limit(10).all()
    
    return jsonify([{
        'seat_number': p.seat_number,
        'floor': p.floor,
        'area': p.area,
        'booking_count': p.count
    } for p in popular])

# ============ 批量优化分配 ============

@app.route('/api/optimize-allocation', methods=['POST'])
def optimize_allocation():
    """批量优化座位分配"""
    requests = request.json['requests']
    
    # 使用遗传算法优化
    allocation = optimizer.optimize_allocation(requests)
    
    result = []
    for i, seat_id in enumerate(allocation):
        seat = Seat.query.get(seat_id)
        result.append({
            'user_id': requests[i]['user_id'],
            'seat_id': seat_id,
            'seat_number': seat.seat_number,
            'floor': seat.floor,
            'area': seat.area
        })
    
    return jsonify(result)

# ============ 初始化数据库 ============

def init_database():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        
        # 检查是否已有数据
        if Seat.query.count() > 0:
            return
        
        # 创建示例座位
        areas = ['A', 'B', 'C', 'D']
        for floor in [1, 2, 3]:
            for area in areas:
                for num in range(1, 26):  # 每个区域25个座位
                    seat = Seat(
                        seat_number=f'{floor}{area}{num:02d}',
                        floor=floor,
                        area=area,
                        has_power=num % 2 == 0,
                        near_window=num <= 5
                    )
                    db.session.add(seat)
        
        db.session.commit()
        print('数据库初始化完成！')

if __name__ == '__main__':
    init_database()
    app.run(debug=True, port=5000)
