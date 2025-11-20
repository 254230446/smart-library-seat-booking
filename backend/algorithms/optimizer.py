import random
import numpy as np
from models import Seat, Booking
from datetime import datetime, timedelta

class GeneticAlgorithmOptimizer:
    """遗传算法座位分配优化"""
    
    def __init__(self, population_size=50, generations=100):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = 0.1
        self.crossover_rate = 0.7
    
    def optimize_allocation(self, bookings_requests):
        """
        优化座位分配
        bookings_requests: [{'user_id': 1, 'preferences': {...}, 'time_slot': ...}, ...]
        """
        available_seats = Seat.query.filter_by(status='available').all()
        
        if not available_seats:
            return []
        
        # 初始化种群
        population = self._initialize_population(bookings_requests, available_seats)
        
        # 进化
        for generation in range(self.generations):
            # 计算适应度
            fitness_scores = [self._fitness(individual, bookings_requests) 
                            for individual in population]
            
            # 选择
            parents = self._selection(population, fitness_scores)
            
            # 交叉
            offspring = self._crossover(parents)
            
            # 变异
            offspring = self._mutation(offspring, available_seats)
            
            # 新一代
            population = offspring
        
        # 返回最优解
        best_idx = np.argmax([self._fitness(ind, bookings_requests) 
                              for ind in population])
        return population[best_idx]
    
    def _initialize_population(self, requests, seats):
        """初始化种群"""
        population = []
        seat_ids = [s.id for s in seats]
        
        for _ in range(self.population_size):
            # 随机分配座位给每个请求
            individual = random.choices(seat_ids, k=len(requests))
            population.append(individual)
        
        return population
    
    def _fitness(self, individual, requests):
        """适应度函数"""
        score = 0
        
        for i, seat_id in enumerate(individual):
            request = requests[i]
            seat = Seat.query.get(seat_id)
            
            # 1. 偏好匹配
            prefs = request.get('preferences', {})
            if prefs.get('has_power') and seat.has_power:
                score += 20
            if prefs.get('near_window') and seat.near_window:
                score += 15
            if prefs.get('floor') == seat.floor:
                score += 10
            
            # 2. 避免座位冲突（同一座位分配给多人）
            if individual.count(seat_id) > 1:
                score -= 100
            
            # 3. 负载均衡（不同区域分布）
            area_distribution = {}
            for sid in individual:
                s = Seat.query.get(sid)
                area_distribution[s.area] = area_distribution.get(s.area, 0) + 1
            
            # 标准差越小越好
            std = np.std(list(area_distribution.values()))
            score -= std * 5
        
        return max(0, score)
    
    def _selection(self, population, fitness_scores):
        """轮盘赌选择"""
        total_fitness = sum(fitness_scores)
        
        if total_fitness == 0:
            return random.choices(population, k=self.population_size)
        
        probabilities = [f / total_fitness for f in fitness_scores]
        parents = random.choices(population, weights=probabilities, 
                                k=self.population_size)
        
        return parents
    
    def _crossover(self, parents):
        """单点交叉"""
        offspring = []
        
        for i in range(0, len(parents), 2):
            parent1 = parents[i]
            parent2 = parents[i + 1] if i + 1 < len(parents) else parents[0]
            
            if random.random() < self.crossover_rate:
                # 单点交叉
                point = random.randint(1, len(parent1) - 1)
                child1 = parent1[:point] + parent2[point:]
                child2 = parent2[:point] + parent1[point:]
                offspring.extend([child1, child2])
            else:
                offspring.extend([parent1, parent2])
        
        return offspring[:self.population_size]
    
    def _mutation(self, population, available_seats):
        """变异"""
        seat_ids = [s.id for s in available_seats]
        
        for individual in population:
            for i in range(len(individual)):
                if random.random() < self.mutation_rate:
                    individual[i] = random.choice(seat_ids)
        
        return population
