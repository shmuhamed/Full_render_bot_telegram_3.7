import os
import logging
import threading
import time
from flask import Flask, request, redirect, url_for, flash, jsonify, render_template_string, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json
import requests
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Создаем Flask приложение
app = Flask(__name__)

# ВАШИ ДАННЫЕ - теперь из переменных окружения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'suvtekin-secret-key-2024-muha-muhamed')
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8586126815:AAHAGyah7Oz-8mHzUcFvRcHV3Dsug3sPT4g')
TELEGRAM_ADMIN_ID = os.environ.get('TELEGRAM_ADMIN_ID', '6349730260')

# База данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cars.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализируем базу данных
db = SQLAlchemy(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    telegram_id = db.Column(db.String(50))
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)

class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class CarModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    brand = db.relationship('Brand', backref='models')
    
    def __repr__(self):
        return self.name

class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    telegram_username = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class PriceCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    min_price_usd = db.Column(db.Float)
    max_price_usd = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return self.name

class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price_usd = db.Column(db.Float, nullable=False)
    price_category_id = db.Column(db.Integer, db.ForeignKey('price_category.id'))
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'))
    model_id = db.Column(db.Integer, db.ForeignKey('car_model.id'))
    year = db.Column(db.Integer)
    mileage_km = db.Column(db.Integer)
    fuel_type = db.Column(db.String(50))
    transmission = db.Column(db.String(50))
    color = db.Column(db.String(50))
    engine_capacity = db.Column(db.Float)
    photo_url1 = db.Column(db.Text)
    photo_url2 = db.Column(db.Text)
    photo_url3 = db.Column(db.Text)
    photo_url4 = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    price_category = db.relationship('PriceCategory')
    brand = db.relationship('Brand')
    model = db.relationship('CarModel')
    
    def __repr__(self):
        return f'{self.title}'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.id'))
    telegram_user_id = db.Column(db.String(50))
    telegram_username = db.Column(db.String(100))
    telegram_first_name = db.Column(db.String(100))
    full_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    car = db.relationship('Car')

class SellRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.String(50))
    telegram_username = db.Column(db.String(100))
    telegram_first_name = db.Column(db.String(100))
    
    car_brand = db.Column(db.String(100))
    car_model = db.Column(db.String(100))
    car_year = db.Column(db.Integer)
    car_mileage = db.Column(db.Integer)
    car_price = db.Column(db.Float)
    car_description = db.Column(db.Text)
    
    phone = db.Column(db.String(50))
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создаем таблицы в контексте приложения
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Таблицы базы данных созданы")
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

    # Создаем админа если нет
    if not User.query.filter_by(username='muha').first():
        try:
            admin = User(
                username='muha',
                password=generate_password_hash('muhamed'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("✅ Создан администратор muha")
        except Exception as e:
            logger.error(f"❌ Ошибка создания администратора: {e}")
            db.session.rollback()
    
    # Создаем ценовые категории если нет
    if PriceCategory.query.count() == 0:
        try:
            categories = [
                ('0-3000$', 0, 3000),
                ('3000-6000$', 3000, 6000),
                ('6000-10000$', 6000, 10000),
                ('10000-20000$', 10000, 20000),
                ('20000+$', 20000, 1000000)
            ]
            
            for name, min_p, max_p in categories:
                if not PriceCategory.query.filter_by(name=name).first():
                    category = PriceCategory(
                        name=name,
                        min_price_usd=min_p,
                        max_price_usd=max_p
                    )
                    db.session.add(category)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(categories)} ценовых категорий")
        except Exception as e:
            logger.error(f"❌ Ошибка создания ценовых категорий: {e}")
            db.session.rollback()
    
    # Создаем бренды если нет
    if Brand.query.count() == 0:
        try:
            brands = ['Toyota', 'Honda', 'BMW', 'Chevrolet', 'Mazda', 'Ford', 'Hyundai', 'Kia', 'Mercedes', 'Audi']
            for brand_name in brands:
                if not Brand.query.filter_by(name=brand_name).first():
                    brand = Brand(name=brand_name)
                    db.session.add(brand)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(brands)} брендов")
        except Exception as e:
            logger.error(f"❌ Ошибка создания брендов: {e}")
            db.session.rollback()
    
    # Создаем модели если нет
    if CarModel.query.count() == 0:
        try:
            models_data = [
                ('Camry', 'Toyota'),
                ('Corolla', 'Toyota'),
                ('RAV4', 'Toyota'),
                ('Civic', 'Honda'),
                ('Accord', 'Honda'),
                ('CR-V', 'Honda'),
                ('X5', 'BMW'),
                ('3 Series', 'BMW'),
                ('Malibu', 'Chevrolet'),
                ('Camaro', 'Chevrolet'),
                ('CX-5', 'Mazda'),
                ('Mazda3', 'Mazda'),
                ('Focus', 'Ford'),
                ('F-150', 'Ford')
            ]
            
            for model_name, brand_name in models_data:
                brand = Brand.query.filter_by(name=brand_name).first()
                if brand and not CarModel.query.filter_by(name=model_name, brand_id=brand.id).first():
                    car_model = CarModel(name=model_name, brand_id=brand.id)
                    db.session.add(car_model)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(models_data)} моделей")
        except Exception as e:
            logger.error(f"❌ Ошибка создания моделей: {e}")
            db.session.rollback()
    
    # Создаем менеджеров если нет
    if Manager.query.count() == 0:
        try:
            managers = [
                ('Мухаммед', 'muhamed', '+996 555 123 456', 'info@suvtekin.kg'),
                ('Алишер', 'alisher_auto', '+996 555 789 012', 'sales@suvtekin.kg'),
                ('Айгерим', 'aigerim_cars', '+996 555 345 678', 'support@suvtekin.kg')
            ]
            
            for name, telegram, phone, email in managers:
                if not Manager.query.filter_by(name=name).first():
                    manager = Manager(
                        name=name,
                        telegram_username=telegram,
                        phone=phone,
                        email=email
                    )
                    db.session.add(manager)
            
            db.session.commit()
            logger.info(f"✅ Создано {len(managers)} менеджеров")
        except Exception as e:
            logger.error(f"❌ Ошибка создания менеджеров: {e}")
            db.session.rollback()
    
    # Создаем примерные автомобили если нет
    if Car.query.count() == 0:
        try:
            # Получаем первые 5 брендов и модели
            brands = Brand.query.limit(5).all()
            
            for i, brand in enumerate(brands):
                models = CarModel.query.filter_by(brand_id=brand.id).limit(2).all()
                
                for j, model in enumerate(models):
                    car = Car(
                        title=f'{brand.name} {model.name} {2020 - i}',
                        description=f'Отличное состояние, полная комплектация. {["Первый владелец", "Без ДТП", "Обслужен у дилера"][j%3]}.',
                        price_usd=15000 + (i * 5000) + (j * 2000),
                        brand_id=brand.id,
                        model_id=model.id,
                        year=2020 - i,
                        mileage_km=30000 + (i * 10000) + (j * 5000),
                        fuel_type=['Бензин', 'Дизель'][i % 2],
                        transmission=['Автомат', 'Механика'][j % 2],
                        color=['Черный', 'Белый', 'Серый', 'Синий'][(i+j) % 4],
                        engine_capacity=1.8 + (i * 0.3),
                        photo_url1='https://images.unsplash.com/photo-1549399542-7e3f8b79c341?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
                        photo_url2='https://images.unsplash.com/photo-1553440569-bcc63803a83d?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
                        photo_url3='https://images.unsplash.com/photo-1555212697-194d092e3b8f?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
                        photo_url4='https://images.unsplash.com/photo-1544636331-e26879cd4d9b?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80',
                        is_active=True
                    )
                    db.session.add(car)
            
            db.session.commit()
            logger.info(f"✅ Создано {Car.query.count()} автомобилей")
        except Exception as e:
            logger.error(f"❌ Ошибка создания автомобилей: {e}")
            db.session.rollback()

# Кастомная View для админки с панелью статистики
class DashboardView(BaseView):
    @expose('/')
    @login_required
    def index(self):
        # Получаем статистику
        total_cars = Car.query.count()
        active_cars = Car.query.filter_by(is_active=True).count()
        new_orders = Order.query.filter_by(status='new').count()
        new_sell_requests = SellRequest.query.filter_by(status='new').count()
        total_brands = Brand.query.count()
        total_models = CarModel.query.count()
        
        # Последние заказы
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
        
        # Последние заявки на продажу
        recent_sell_requests = SellRequest.query.order_by(SellRequest.created_at.desc()).limit(5).all()
        
        # Статистика по брендам
        brands_stats = []
        brands = Brand.query.all()
        for brand in brands:
            car_count = Car.query.filter_by(brand_id=brand.id, is_active=True).count()
            if car_count > 0:
                brands_stats.append({
                    'name': brand.name,
                    'count': car_count
                })
        
        # Группировка по ценовым категориям
        price_stats = []
        categories = PriceCategory.query.all()
        for category in categories:
            car_count = Car.query.filter(
                Car.price_usd >= category.min_price_usd,
                Car.price_usd <= category.max_price_usd,
                Car.is_active == True
            ).count()
            price_stats.append({
                'name': category.name,
                'count': car_count
            })
        
        return self.render('admin/dashboard.html',
                          total_cars=total_cars,
                          active_cars=active_cars,
                          new_orders=new_orders,
                          new_sell_requests=new_sell_requests,
                          total_brands=total_brands,
                          total_models=total_models,
                          recent_orders=recent_orders,
                          recent_sell_requests=recent_sell_requests,
                          brands_stats=brands_stats,
                          price_stats=price_stats)

# Кастомный ModelView с рабочими кнопками
class CustomModelView(ModelView):
    # Разрешаем все действия по умолчанию
    can_create = True
    can_edit = True
    can_delete = True
    can_export = True
    can_view_details = True
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

# Кастомные View для каждой модели
class CarAdminView(CustomModelView):
    column_list = ['id', 'title', 'price_usd', 'brand', 'model', 'year', 'mileage_km', 'is_active']
    column_searchable_list = ['title', 'description']
    column_filters = ['year', 'is_active', 'price_usd', 'brand', 'fuel_type']
    column_labels = {
        'price_usd': 'Цена ($)',
        'mileage_km': 'Пробег (км)',
        'brand': 'Бренд',
        'model': 'Модель',
        'price_category': 'Категория цены'
    }
    
    form_columns = ['title', 'description', 'price_usd', 'price_category', 'brand', 'model', 
                   'year', 'mileage_km', 'fuel_type', 'transmission', 'color', 
                   'engine_capacity', 'photo_url1', 'photo_url2', 'photo_url3', 'photo_url4', 'is_active']
    
    form_choices = {
        'fuel_type': [
            ('Бензин', 'Бензин'),
            ('Дизель', 'Дизель'),
            ('Газ', 'Газ'),
            ('Электричество', 'Электричество'),
            ('Гибрид', 'Гибрид'),
            ('Гибрид (бензин-электричество)', 'Гибрид (бензин-электричество)'),
            ('Гибрид (дизель-электричество)', 'Гибрид (дизель-электричество)'),
            ('Газ/бензин', 'Газ/бензин')
        ],
        'transmission': [
            ('Автомат', 'Автомат'),
            ('Механика', 'Механика'),
            ('Вариатор', 'Вариатор'),
            ('Робот', 'Робот')
        ],
        'color': [
            ('Черный', 'Черный'),
            ('Белый', 'Белый'),
            ('Серый', 'Серый'),
            ('Синий', 'Синий'),
            ('Красный', 'Красный'),
            ('Зеленый', 'Зеленый'),
            ('Желтый', 'Желтый'),
            ('Серебристый', 'Серебристый'),
            ('Бежевый', 'Бежевый'),
            ('Коричневый', 'Коричневый')
        ]
    }
    
    def on_model_change(self, form, model, is_created):
        # Автоматически определяем ценовую категорию
        if model.price_usd is not None:
            categories = PriceCategory.query.filter_by(is_active=True).all()
            for category in categories:
                if category.min_price_usd <= model.price_usd <= category.max_price_usd:
                    model.price_category_id = category.id
                    break
        
        # Обновляем title если есть бренд и модель
        if model.brand and model.model and model.year:
            model.title = f"{model.brand.name} {model.model.name} {model.year}"

class BrandAdminView(CustomModelView):
    column_list = ['id', 'name', 'is_active', 'created_at']
    form_columns = ['name', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active']
    form_args = {
        'name': {
            'label': 'Название бренда',
            'description': 'Например: Toyota, BMW'
        }
    }

class CarModelAdminView(CustomModelView):
    column_list = ['id', 'name', 'brand', 'is_active', 'created_at']
    form_columns = ['name', 'brand', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active', 'brand']
    form_args = {
        'name': {
            'label': 'Название модели',
            'description': 'Например: Camry, X5'
        }
    }

class PriceCategoryAdminView(CustomModelView):
    column_list = ['id', 'name', 'min_price_usd', 'max_price_usd', 'is_active']
    form_columns = ['name', 'min_price_usd', 'max_price_usd', 'is_active']
    column_searchable_list = ['name']
    column_filters = ['is_active']

class ManagerAdminView(CustomModelView):
    column_list = ['id', 'name', 'telegram_username', 'phone', 'email', 'is_active']
    form_columns = ['name', 'telegram_username', 'phone', 'email', 'is_active']
    column_searchable_list = ['name', 'phone', 'email']
    column_filters = ['is_active']

class OrderAdminView(CustomModelView):
    column_list = ['id', 'car', 'full_name', 'phone', 'status', 'created_at']
    form_columns = ['status', 'phone', 'full_name']
    column_filters = ['status', 'created_at']
    column_searchable_list = ['full_name', 'phone']
    can_create = False  # Заказы создаются только через бота

class SellRequestAdminView(CustomModelView):
    column_list = ['id', 'telegram_user_id', 'telegram_username', 'car_brand', 'car_model', 
                   'car_price', 'phone', 'status', 'created_at']
    form_columns = ['status', 'phone', 'car_description']
    column_filters = ['status', 'created_at']
    column_searchable_list = ['telegram_username', 'car_brand', 'car_model', 'phone']
    can_create = False  # Заявки создаются только через бота
    
    column_labels = {
        'telegram_user_id': 'TG ID',
        'telegram_username': 'TG Username',
        'car_brand': 'Марка',
        'car_model': 'Модель',
        'car_price': 'Цена',
        'phone': 'Телефон',
        'status': 'Статус',
        'created_at': 'Дата'
    }

class UserAdminView(CustomModelView):
    column_list = ['id', 'username', 'role', 'telegram_id', 'created_at']
    form_columns = ['username', 'password', 'role', 'telegram_id']
    column_searchable_list = ['username']
    column_filters = ['role', 'created_at']
    
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password = generate_password_hash(form.password.data)

# Создаем админку с кастомным шаблоном
admin = Admin(app, name='🚗 Suvtekin Auto', template_mode='bootstrap3', url='/admin',
              index_view=DashboardView(name='📊 Дашборд', endpoint='dashboard', url='/admin'))

# Добавляем все модели с уникальными endpoint именами
admin.add_view(CarAdminView(Car, db.session, name='🚗 Автомобили', endpoint='cars'))
admin.add_view(BrandAdminView(Brand, db.session, name='🏭 Бренды', endpoint='brands', category='Справочники'))
admin.add_view(CarModelAdminView(CarModel, db.session, name='📋 Модели', endpoint='carmodels', category='Справочники'))
admin.add_view(PriceCategoryAdminView(PriceCategory, db.session, name='💰 Категории цен', endpoint='pricecategories', category='Справочники'))
admin.add_view(ManagerAdminView(Manager, db.session, name='👨‍💼 Менеджеры', endpoint='managers', category='Персонал'))
admin.add_view(OrderAdminView(Order, db.session, name='🛒 Заказы', endpoint='orders', category='Заявки'))
admin.add_view(SellRequestAdminView(SellRequest, db.session, name='💰 Заявки на продажу', endpoint='sellrequests', category='Заявки'))
admin.add_view(UserAdminView(User, db.session, name='👤 Пользователи', endpoint='users', category='Система'))

# Переопределяем базовый шаблон админки для добавления статистики
@app.context_processor
def inject_stats():
    if current_user.is_authenticated and current_user.role == 'admin':
        stats = {
            'total_cars': Car.query.count(),
            'active_cars': Car.query.filter_by(is_active=True).count(),
            'new_orders': Order.query.filter_by(status='new').count(),
            'new_sell_requests': SellRequest.query.filter_by(status='new').count(),
        }
        return {'stats': stats}
    return {}

# Страница быстрого добавления авто
@app.route('/admin/quick-add', methods=['GET', 'POST'])
@login_required
def quick_add():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            title = request.form.get('title')
            price_usd = float(request.form.get('price_usd', 0))
            brand_name = request.form.get('brand_name', '').strip()
            brand_id = request.form.get('brand_id')
            model_name = request.form.get('model_name', '').strip()
            model_id = request.form.get('model_id')
            year = request.form.get('year')
            mileage_km = request.form.get('mileage_km')
            description = request.form.get('description', '')
            photo_url1 = request.form.get('photo_url1', '')
            photo_url2 = request.form.get('photo_url2', '')
            photo_url3 = request.form.get('photo_url3', '')
            photo_url4 = request.form.get('photo_url4', '')
            fuel_type = request.form.get('fuel_type', '')
            transmission = request.form.get('transmission', '')
            color = request.form.get('color', '')
            engine_capacity = request.form.get('engine_capacity')
            
            # Определяем бренд
            final_brand_id = None
            if brand_name:
                # Создаем новый бренд
                brand = Brand(name=brand_name, is_active=True)
                db.session.add(brand)
                db.session.flush()
                final_brand_id = brand.id
            elif brand_id:
                final_brand_id = int(brand_id)
            else:
                flash('Необходимо указать бренд', 'danger')
                return redirect(url_for('quick_add'))
            
            # Определяем модель
            final_model_id = None
            if model_name:
                # Создаем новую модель
                model = CarModel(name=model_name, brand_id=final_brand_id, is_active=True)
                db.session.add(model)
                db.session.flush()
                final_model_id = model.id
            elif model_id:
                final_model_id = int(model_id)
            
            # Создаем автомобиль
            car = Car(
                title=title,
                description=description,
                price_usd=price_usd,
                brand_id=final_brand_id,
                model_id=final_model_id,
                year=int(year) if year else None,
                mileage_km=int(mileage_km) if mileage_km else None,
                fuel_type=fuel_type,
                transmission=transmission,
                color=color,
                engine_capacity=float(engine_capacity) if engine_capacity else None,
                photo_url1=photo_url1,
                photo_url2=photo_url2,
                photo_url3=photo_url3,
                photo_url4=photo_url4,
                is_active=True
            )
            
            # Автоматически определяем ценовую категорию
            categories = PriceCategory.query.filter_by(is_active=True).all()
            for category in categories:
                if category.min_price_usd <= car.price_usd <= category.max_price_usd:
                    car.price_category_id = category.id
                    break
            
            db.session.add(car)
            db.session.commit()
            
            flash(f'🚗 Автомобиль "{title}" успешно добавлен!', 'success')
            return redirect(url_for('admin.index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка добавления автомобиля: {e}")
            flash(f'❌ Ошибка добавления: {str(e)}', 'danger')
    
    # Получаем данные для формы
    brands = Brand.query.filter_by(is_active=True).all()
    models = CarModel.query.filter_by(is_active=True).all()
    price_categories = PriceCategory.query.filter_by(is_active=True).all()
    
    return render_template_string(''' 
<!DOCTYPE html>
<html>
<head>
    <title>🚗 Быстрое добавление - Suvtekin Auto</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1200px; margin-top: 30px; }
        .glass-card { background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px); border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
        .header-gradient { background: linear-gradient(90deg, #007bff, #00d4ff); color: white; }
        .stats-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); transition: transform 0.3s; }
        .stats-card:hover { transform: translateY(-5px); }
        .stats-icon { font-size: 2.5rem; margin-bottom: 15px; }
        .btn-animated { background: linear-gradient(90deg, #007bff, #00d4ff); color: white; border: none; padding: 12px 30px; border-radius: 50px; font-weight: bold; transition: all 0.3s; }
        .btn-animated:hover { transform: scale(1.05); box-shadow: 0 10px 20px rgba(0,123,255,0.3); }
        .form-section { background: #f8f9fa; border-radius: 15px; padding: 25px; margin-bottom: 25px; border: 1px solid #e9ecef; }
        .nav-tabs .nav-link.active { background: #007bff; color: white; border-radius: 10px 10px 0 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="glass-card">
            <div class="header-gradient p-4">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h1 class="mb-0"><i class="fas fa-car"></i> Быстрое добавление автомобиля</h1>
                        <p class="mb-0 opacity-75">Добавьте новый автомобиль за несколько минут</p>
                    </div>
                    <a href="{{ url_for('admin.index') }}" class="btn btn-light btn-lg">
                        <i class="fas fa-arrow-left"></i> Назад в админку
                    </a>
                </div>
            </div>
            
            <div class="p-4">
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show">
                                <i class="fas fa-{{ 'check-circle' if category == 'success' else 'exclamation-circle' }}"></i>
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                <!-- Статистика вверху -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="stats-card text-center">
                            <div class="stats-icon text-primary">
                                <i class="fas fa-car"></i>
                            </div>
                            <h3>{{ Car.query.count() }}</h3>
                            <p class="text-muted">Всего авто</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card text-center">
                            <div class="stats-icon text-success">
                                <i class="fas fa-check-circle"></i>
                            </div>
                            <h3>{{ Car.query.filter_by(is_active=True).count() }}</h3>
                            <p class="text-muted">Активных авто</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card text-center">
                            <div class="stats-icon text-warning">
                                <i class="fas fa-shopping-cart"></i>
                            </div>
                            <h3>{{ Order.query.filter_by(status='new').count() }}</h3>
                            <p class="text-muted">Новых заказов</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card text-center">
                            <div class="stats-icon text-info">
                                <i class="fas fa-money-bill-wave"></i>
                            </div>
                            <h3>{{ SellRequest.query.filter_by(status='new').count() }}</h3>
                            <p class="text-muted">Новых заявок</p>
                        </div>
                    </div>
                </div>
                
                <form method="POST">
                    <!-- Основная информация -->
                    <div class="form-section">
                        <h3 class="mb-4"><i class="fas fa-info-circle text-primary"></i> Основная информация</h3>
                        <div class="row">
                            <div class="col-md-8 mb-3">
                                <label class="form-label fw-bold">Название автомобиля *</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-car"></i></span>
                                    <input type="text" class="form-control" name="title" required placeholder="Toyota Camry 2020">
                                </div>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label fw-bold">Цена ($) *</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-dollar-sign"></i></span>
                                    <input type="number" step="0.01" class="form-control" name="price_usd" required placeholder="15000">
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label fw-bold">Описание</label>
                            <div class="input-group">
                                <span class="input-group-text"><i class="fas fa-align-left"></i></span>
                                <textarea class="form-control" name="description" rows="3" placeholder="Отличное состояние, полная комплектация..."></textarea>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Бренд и модель -->
                    <div class="form-section">
                        <h3 class="mb-4"><i class="fas fa-tags text-success"></i> Бренд и модель</h3>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Выберите существующий бренд:</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-copyright"></i></span>
                                    <select class="form-control" name="brand_id" id="brandSelect" onchange="updateModels()">
                                        <option value="">-- Выберите бренд --</option>
                                        {% for brand in brands %}
                                        <option value="{{ brand.id }}">{{ brand.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Или добавьте новый бренд:</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-plus-circle"></i></span>
                                    <input type="text" class="form-control" name="brand_name" placeholder="Название нового бренда">
                                </div>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Выберите модель:</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-list"></i></span>
                                    <select class="form-control" name="model_id" id="modelSelect">
                                        <option value="">-- Сначала выберите бренд --</option>
                                        {% for model in models %}
                                        <option value="{{ model.id }}" data-brand="{{ model.brand_id }}">{{ model.brand.name }} - {{ model.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Или добавьте новую модель:</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-plus-circle"></i></span>
                                    <input type="text" class="form-control" name="model_name" placeholder="Название новой модели">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Характеристики -->
                    <div class="form-section">
                        <h3 class="mb-4"><i class="fas fa-cogs text-warning"></i> Характеристики</h3>
                        <div class="row">
                            <div class="col-md-3 mb-3">
                                <label class="form-label">Год выпуска</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-calendar"></i></span>
                                    <input type="number" class="form-control" name="year" min="1900" max="2024" placeholder="2020">
                                </div>
                            </div>
                            <div class="col-md-3 mb-3">
                                <label class="form-label">Пробег (км)</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-tachometer-alt"></i></span>
                                    <input type="number" class="form-control" name="mileage_km" placeholder="50000">
                                </div>
                            </div>
                            <div class="col-md-3 mb-3">
                                <label class="form-label">Объем двигателя (л)</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-gas-pump"></i></span>
                                    <input type="number" step="0.1" class="form-control" name="engine_capacity" placeholder="2.0">
                                </div>
                            </div>
                            <div class="col-md-3 mb-3">
                                <label class="form-label">Цвет</label>
                                <select class="form-control" name="color">
                                    <option value="">-- Выберите цвет --</option>
                                    <option value="Черный">Черный</option>
                                    <option value="Белый">Белый</option>
                                    <option value="Серый">Серый</option>
                                    <option value="Синий">Синий</option>
                                    <option value="Красный">Красный</option>
                                </select>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Тип топлива</label>
                                <select class="form-control" name="fuel_type">
                                    <option value="">-- Выберите --</option>
                                    <option value="Бензин">Бензин</option>
                                    <option value="Дизель">Дизель</option>
                                    <option value="Газ">Газ</option>
                                    <option value="Электричество">Электричество</option>
                                    <option value="Гибрид">Гибрид</option>
                                </select>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Коробка передач</label>
                                <select class="form-control" name="transmission">
                                    <option value="">-- Выберите --</option>
                                    <option value="Автомат">Автомат</option>
                                    <option value="Механика">Механика</option>
                                    <option value="Вариатор">Вариатор</option>
                                    <option value="Робот">Робот</option>
                                </select>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Категория цены</label>
                                <select class="form-control" name="price_category">
                                    <option value="">-- Автоматически --</option>
                                    {% for category in price_categories %}
                                    <option value="{{ category.id }}">{{ category.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Фотографии -->
                    <div class="form-section">
                        <h3 class="mb-4"><i class="fas fa-camera text-info"></i> Фотографии (URL)</h3>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label fw-bold">Фото 1 (главное) *</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-image"></i></span>
                                    <input type="url" class="form-control" name="photo_url1" placeholder="https://example.com/photo1.jpg" required>
                                </div>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Фото 2</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-image"></i></span>
                                    <input type="url" class="form-control" name="photo_url2" placeholder="https://example.com/photo2.jpg">
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Фото 3</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-image"></i></span>
                                    <input type="url" class="form-control" name="photo_url3" placeholder="https://example.com/photo3.jpg">
                                </div>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Фото 4</label>
                                <div class="input-group">
                                    <span class="input-group-text"><i class="fas fa-image"></i></span>
                                    <input type="url" class="form-control" name="photo_url4" placeholder="https://example.com/photo4.jpg">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="text-center mt-4">
                        <button type="submit" class="btn btn-animated btn-lg px-5">
                            <i class="fas fa-plus-circle me-2"></i> Добавить автомобиль
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        function updateModels() {
            const brandId = document.getElementById('brandSelect').value;
            const modelSelect = document.getElementById('modelSelect');
            
            for (let i = 0; i < modelSelect.options.length; i++) {
                const option = modelSelect.options[i];
                const brandData = option.getAttribute('data-brand');
                
                if (!brandId || brandData === brandId || option.value === "") {
                    option.style.display = '';
                } else {
                    option.style.display = 'none';
                }
            }
            
            modelSelect.value = "";
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            updateModels();
        });
    </script>
</body>
</html>
    ''', brands=brands, models=models, price_categories=price_categories)

# TELEGRAM БОТ - ИСПРАВЛЕННЫЙ
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Полные словари для языков
TEXTS = {
    'ru': {
        'choose_language': 'Выберите язык:\n\nTilni tanlang:',
        'welcome': '🚗 Добро пожаловать в Suvtekin Auto!\n\nВыберите действие:',
        'help': '📋 Используйте кнопки ниже для навигации по боту',
        'main_menu': '📌 Главное меню:',
        'show_cars': '🚗 Посмотреть авто',
        'price_categories': '💰 Категории цен',
        'select_by_brand': '🏭 Поиск по марке',
        'contact_manager': '📞 Контакты',
        'sell_car': '💰 Продать авто',
        'help_btn': 'ℹ️ Помощь',
        'no_cars': '🚗 Автомобилей нет в наличии',
        'car_info': '🚗 *{title}*\n\n💰 *Цена:* ${price:,.0f}\n📏 *Пробег:* {mileage:,} км\n🏭 *Марка:* {brand}\n📅 *Год:* {year}\n⛽ *Топливо:* {fuel}\n⚙️ *КПП:* {transmission}\n🎨 *Цвет:* {color}\n🔧 *Объем:* {engine} л\n\n{description}',
        'order_btn': '🛒 Заказать',
        'order_phone': '📞 Введите ваш номер телефона для связи:',
        'order_success': '✅ Заказ оформлен! Менеджер свяжется с вами.',
        'choose_category': 'Выберите категорию цены:',
        'choose_brand': 'Выберите марку автомобиля:',
        'choose_model': 'Выберите модель:',
        'managers': '📞 *Наши менеджеры:*\n\n{managers}',
        'sell_car_welcome': '💰 *Продать автомобиль*\n\nВыберите марку вашего авто:',
        'other_brand': '➡️ Другая марка',
        'sell_car_model': 'Введите модель автомобиля:',
        'sell_car_year': 'Введите год выпуска автомобиля:',
        'sell_car_mileage': 'Введите пробег (в км):',
        'sell_car_price': 'Введите желаемую цену ($):',
        'sell_car_description': 'Опишите состояние автомобиля:',
        'sell_car_phone': 'Введите ваш номер телефона:',
        'sell_car_success': '✅ Заявка отправлена! Менеджер свяжется с вами.',
        'back': '🔙 Назад',
        'cancel': '❌ Отмена',
        'all_brands': 'Все марки',
        'error': '❌ Произошла ошибка. Попробуйте еще раз.',
        'select_brand': 'Выберите марку:',
        'show_all_cars': '📋 Все автомобили',
        'brands_title': '🏭 Популярные марки:',
        'new_cars': '🆕 Новые поступления',
        'popular_cars': '🔥 Популярные авто',
        'choose_brand_sell': '🏭 Выберите марку автомобиля для продажи:'
    },
    'uz': {
        'choose_language': 'Tilni tanlang:\n\nВыберите язык:',
        'welcome': '🚗 Suvtekin Auto ga xush kelibsiz!\n\nAmalni tanlang:',
        'help': '📋 Bot orqali harakatlanish uchun pastdagi tugmalardan foydalaning',
        'main_menu': '📌 Asosiy menyu:',
        'show_cars': '🚗 Avtomobillarni ko\'rish',
        'price_categories': '💰 Narx kategoriyalari',
        'select_by_brand': '🏭 Marka bo\'yicha qidirish',
        'contact_manager': '📞 Kontaktlar',
        'sell_car': '💰 Avtomobil sotish',
        'help_btn': 'ℹ️ Yordam',
        'no_cars': '🚗 Mavjud avtomobillar yo\'q',
        'car_info': '🚗 *{title}*\n\n💰 *Narx:* ${price:,.0f}\n📏 *Yurgan:* {mileage:,} km\n🏭 *Marka:* {brand}\n📅 *Yil:* {year}\n⛽ *Yoqilg\'i:* {fuel}\n⚙️ *Uzatma:* {transmission}\n🎨 *Rang:* {color}\n🔧 *Hajm:* {engine} l\n\n{description}',
        'order_btn': '🛒 Buyurtma',
        'order_phone': '📞 Aloqa uchun telefon raqamingizni kiriting:',
        'order_success': '✅ Buyurtma qabul qilindi! Menejer siz bilan bog\'lanadi.',
        'choose_category': 'Narx kategoriyasini tanlang:',
        'choose_brand': 'Avtomobil markasini tanlang:',
        'choose_model': 'Modelni tanlang:',
        'managers': '📞 *Bizning menejerlarimiz:*\n\n{managers}',
        'sell_car_welcome': '💰 *Avtomobil sotish*\n\nAvtomobilingiz markasini tanlang:',
        'other_brand': '➡️ Boshqa marka',
        'sell_car_model': 'Avtomobil modelini kiriting:',
        'sell_car_year': 'Avtomobil ishlab chiqarilgan yilini kiriting:',
        'sell_car_mileage': 'Yurgan masofani kiriting (km):',
        'sell_car_price': 'Istalgan narxni kiriting ($):',
        'sell_car_description': 'Avtomobil holatini tasvirlang:',
        'sell_car_phone': 'Telefon raqamingizni kiriting:',
        'sell_car_success': '✅ Ariza yuborildi! Menejer siz bilan bog\'lanadi.',
        'back': '🔙 Orqaga',
        'cancel': '❌ Bekor qilish',
        'all_brands': 'Barcha markalar',
        'error': '❌ Xatolik yuz berdi. Qaytadan urinib ko\'ring.',
        'select_brand': 'Markani tanlang:',
        'show_all_cars': '📋 Barcha avtomobillar',
        'brands_title': '🏭 Mashhur markalar:',
        'new_cars': '🆕 Yangi qo\'shilganlar',
        'popular_cars': '🔥 Mashhur avtomobillar',
        'choose_brand_sell': '🏭 Sotish uchun avtomobil markingizni tanlang:'
    }
}

# Словари для состояний
user_languages = {}
user_states = {}
user_data = {}

def get_language(chat_id):
    return user_languages.get(chat_id, 'ru')

def t(chat_id, key):
    return TEXTS[get_language(chat_id)].get(key, key)

def send_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    url = f"{BASE_URL}/sendMessage"
    params = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, params=params, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return None

def send_photo(chat_id, photo_url, caption, reply_markup=None):
    if not photo_url:
        send_message(chat_id, caption, reply_markup)
        return
    
    url = f"{BASE_URL}/sendPhoto"
    params = {'chat_id': chat_id, 'photo': photo_url, 'caption': caption, 'parse_mode': 'Markdown'}
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    try:
        response = requests.post(url, params=params, timeout=10)
        if response.status_code != 200:
            send_message(chat_id, caption, reply_markup)
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        send_message(chat_id, caption, reply_markup)

def get_language_menu():
    return {
        'keyboard': [
            ['🇷🇺 Русский', '🇺🇿 O\'zbek']
        ],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }

def get_main_menu(chat_id):
    keyboard = [
        [t(chat_id, 'show_cars'), t(chat_id, 'price_categories')],
        [t(chat_id, 'select_by_brand'), t(chat_id, 'contact_manager')],
        [t(chat_id, 'sell_car'), t(chat_id, 'help_btn')]
    ]
    return {
        'keyboard': keyboard,
        'resize_keyboard': True,
        'one_time_keyboard': False
    }

def get_cancel_menu(chat_id):
    return {
        'keyboard': [[t(chat_id, 'cancel')]],
        'resize_keyboard': True,
        'one_time_keyboard': True
    }

def get_order_button(chat_id, car_id):
    return {
        'inline_keyboard': [[
            {'text': t(chat_id, 'order_btn'), 'callback_data': f'order_{car_id}'}
        ]]
    }

def get_brand_menu(chat_id, action='view'):
    """Меню выбора бренда для просмотра или продажи"""
    with app.app_context():
        brands = Brand.query.filter_by(is_active=True).all()
        keyboard = []
        
        # Создаем кнопки брендов
        for i in range(0, len(brands), 2):
            row = []
            if i < len(brands):
                callback_data = f'brand_view_{brands[i].id}' if action == 'view' else f'brand_sell_{brands[i].id}'
                row.append({'text': brands[i].name, 'callback_data': callback_data})
            if i + 1 < len(brands):
                callback_data = f'brand_view_{brands[i+1].id}' if action == 'view' else f'brand_sell_{brands[i+1].id}'
                row.append({'text': brands[i+1].name, 'callback_data': callback_data})
            if row:
                keyboard.append(row)
        
        # Добавляем кнопку "Все бренды" только для просмотра
        if action == 'view':
            keyboard.append([{'text': t(chat_id, 'all_brands'), 'callback_data': 'brand_all'}])
        
        keyboard.append([{'text': t(chat_id, 'back'), 'callback_data': 'back_menu'}])
        return {'inline_keyboard': keyboard}

def get_category_menu(chat_id):
    with app.app_context():
        categories = PriceCategory.query.filter_by(is_active=True).all()
        keyboard = []
        
        for category in categories:
            count = Car.query.filter(
                Car.price_usd >= category.min_price_usd,
                Car.price_usd <= category.max_price_usd,
                Car.is_active == True
            ).count()
            if count > 0:
                keyboard.append([{'text': f"{category.name} ({count})", 'callback_data': f'cat_{category.id}'}])
        
        keyboard.append([{'text': t(chat_id, 'back'), 'callback_data': 'back_menu'}])
        return {'inline_keyboard': keyboard}

# Основной обработчик вебхука
@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    try:
        update = request.get_json()
        
        if 'callback_query' in update:
            handle_callback(update['callback_query'])
        elif 'message' in update:
            handle_message(update['message'])
        
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}")
        return jsonify({'ok': False, 'error': str(e)})

def handle_callback(callback_query):
    try:
        data = callback_query['data']
        chat_id = callback_query['message']['chat']['id']
        
        if data == 'back_menu':
            send_message(chat_id, t(chat_id, 'main_menu'), get_main_menu(chat_id))
        
        elif data == 'brand_all':
            show_cars(chat_id)
        
        elif data.startswith('brand_view_'):
            brand_id = int(data.split('_')[2])
            show_cars_by_brand(chat_id, brand_id)
        
        elif data.startswith('brand_sell_'):
            brand_id = int(data.split('_')[2])
            with app.app_context():
                brand = Brand.query.get(brand_id)
            if brand:
                user_states[chat_id] = {'action': 'sell_car', 'step': 'model'}
                user_data[chat_id] = {'brand': brand.name}
                send_message(chat_id, t(chat_id, 'sell_car_model'), get_cancel_menu(chat_id))
        
        elif data.startswith('order_'):
            car_id = int(data.split('_')[1])
            start_order(chat_id, car_id)
        
        elif data.startswith('cat_'):
            category_id = int(data.split('_')[1])
            show_cars(chat_id, 'category', category_id)
        
        # Ответ на callback
        url = f"{BASE_URL}/answerCallbackQuery"
        params = {'callback_query_id': callback_query['id']}
        requests.post(url, params=params)
        
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")
        send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def handle_message(message):
    try:
        chat_id = message['chat']['id']
        text = message.get('text', '')
        username = message['chat'].get('username', '')
        first_name = message['chat'].get('first_name', '')
        
        # Проверяем выбран ли язык
        if chat_id not in user_languages:
            if text in ['🇷🇺 Русский', 'Русский', 'RU', 'ru', '/start']:
                handle_language_selection(chat_id, 'ru')
            elif text in ['🇺🇿 O\'zbek', 'O\'zbek', 'UZ', 'uz']:
                handle_language_selection(chat_id, 'uz')
            else:
                handle_start(chat_id, first_name)
            return
        
        # Получаем состояние пользователя
        state = user_states.get(chat_id, {})
        action = state.get('action')
        
        # Отмена
        if text == t(chat_id, 'cancel'):
            user_states.pop(chat_id, None)
            user_data.pop(chat_id, None)
            send_message(chat_id, t(chat_id, 'main_menu'), get_main_menu(chat_id))
            return
        
        # Обработка процесса продажи
        if action == 'sell_car':
            step = state.get('step')
            data = user_data.get(chat_id, {})
            
            if step == 'brand':
                if text == t(chat_id, 'other_brand'):
                    user_states[chat_id]['step'] = 'brand_other'
                    send_message(chat_id, "Введите марку вашего автомобиля:", get_cancel_menu(chat_id))
                else:
                    with app.app_context():
                        brand = Brand.query.filter_by(name=text, is_active=True).first()
                    if brand:
                        data['brand'] = text
                        user_states[chat_id]['step'] = 'model'
                        send_message(chat_id, t(chat_id, 'sell_car_model'), get_cancel_menu(chat_id))
                    else:
                        data['brand'] = text
                        user_states[chat_id]['step'] = 'model'
                        send_message(chat_id, t(chat_id, 'sell_car_model'), get_cancel_menu(chat_id))
            
            elif step == 'brand_other':
                data['brand'] = text
                user_states[chat_id]['step'] = 'model'
                send_message(chat_id, t(chat_id, 'sell_car_model'), get_cancel_menu(chat_id))
            
            elif step == 'model':
                data['model'] = text
                user_states[chat_id]['step'] = 'year'
                send_message(chat_id, t(chat_id, 'sell_car_year'), get_cancel_menu(chat_id))
            
            elif step == 'year':
                try:
                    data['year'] = int(text)
                    user_states[chat_id]['step'] = 'mileage'
                    send_message(chat_id, t(chat_id, 'sell_car_mileage'), get_cancel_menu(chat_id))
                except:
                    send_message(chat_id, "Пожалуйста, введите правильный год (например: 2020)")
            
            elif step == 'mileage':
                try:
                    data['mileage'] = int(text)
                    user_states[chat_id]['step'] = 'price'
                    send_message(chat_id, t(chat_id, 'sell_car_price'), get_cancel_menu(chat_id))
                except:
                    send_message(chat_id, "Пожалуйста, введите правильный пробег (например: 50000)")
            
            elif step == 'price':
                try:
                    data['price'] = float(text)
                    user_states[chat_id]['step'] = 'description'
                    send_message(chat_id, t(chat_id, 'sell_car_description'), get_cancel_menu(chat_id))
                except:
                    send_message(chat_id, "Пожалуйста, введите правильную цену (например: 15000)")
            
            elif step == 'description':
                data['description'] = text
                user_states[chat_id]['step'] = 'phone'
                send_message(chat_id, t(chat_id, 'sell_car_phone'), get_cancel_menu(chat_id))
            
            elif step == 'phone':
                data['phone'] = text
                complete_sell(chat_id, username, first_name)
            
            user_data[chat_id] = data
            return
        
        # Обработка заказа с телефоном
        elif action == 'order':
            car_id = state.get('car_id')
            if car_id:
                complete_order(chat_id, car_id, text, username, first_name)
            return
        
        # Обработка команд
        if text == '/start':
            handle_start(chat_id, first_name)
        elif text == '/help' or text == t(chat_id, 'help_btn'):
            send_message(chat_id, t(chat_id, 'help'), get_main_menu(chat_id))
        elif text == t(chat_id, 'show_cars'):
            show_cars(chat_id)
        elif text == t(chat_id, 'price_categories'):
            send_message(chat_id, t(chat_id, 'choose_category'), get_category_menu(chat_id))
        elif text == t(chat_id, 'select_by_brand'):
            send_message(chat_id, t(chat_id, 'select_brand'), get_brand_menu(chat_id, 'view'))
        elif text == t(chat_id, 'contact_manager'):
            show_managers(chat_id)
        elif text == t(chat_id, 'sell_car'):
            start_sell_car(chat_id)
        elif text.startswith('/'):
            send_message(chat_id, t(chat_id, 'help'), get_main_menu(chat_id))
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def handle_start(chat_id, first_name):
    user_languages.pop(chat_id, None)
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)
    
    message = TEXTS['ru']['choose_language']
    send_message(chat_id, message, get_language_menu())

def handle_language_selection(chat_id, language):
    user_languages[chat_id] = language
    send_message(chat_id, TEXTS[language]['welcome'], get_main_menu(chat_id))

def show_cars(chat_id, filter_type=None, filter_id=None):
    try:
        with app.app_context():
            query = Car.query.filter_by(is_active=True)
            
            if filter_type == 'category' and filter_id:
                category = PriceCategory.query.get(filter_id)
                if category:
                    query = query.filter(
                        Car.price_usd >= category.min_price_usd,
                        Car.price_usd <= category.max_price_usd
                    )
            
            cars = query.order_by(Car.created_at.desc()).limit(5).all()
            
            if not cars:
                send_message(chat_id, t(chat_id, 'no_cars'), get_main_menu(chat_id))
                return
            
            for car in cars:
                brand_name = car.brand.name if car.brand else ""
                model_name = car.model.name if car.model else ""
                full_brand = f"{brand_name} {model_name}".strip()
                
                caption = t(chat_id, 'car_info').format(
                    title=car.title,
                    price=car.price_usd,
                    mileage=car.mileage_km,
                    brand=full_brand,
                    year=car.year,
                    fuel=car.fuel_type or 'Не указано',
                    transmission=car.transmission or 'Не указано',
                    color=car.color or 'Не указан',
                    engine=car.engine_capacity or 'Не указан',
                    description=car.description or 'Нет описания'
                )
                
                photo_url = car.photo_url1 or car.photo_url2 or car.photo_url3 or car.photo_url4
                send_photo(chat_id, photo_url, caption, get_order_button(chat_id, car.id))
                
                # Отправляем остальные фото
                other_photos = []
                if car.photo_url2:
                    other_photos.append(car.photo_url2)
                if car.photo_url3:
                    other_photos.append(car.photo_url3)
                if car.photo_url4:
                    other_photos.append(car.photo_url4)
                
                for photo in other_photos:
                    send_photo(chat_id, photo, "")
                    
    except Exception as e:
        logger.error(f"Ошибка показа авто: {e}")
        send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def show_cars_by_brand(chat_id, brand_id):
    try:
        with app.app_context():
            cars = Car.query.filter_by(brand_id=brand_id, is_active=True).order_by(Car.created_at.desc()).limit(5).all()
            
            if not cars:
                send_message(chat_id, t(chat_id, 'no_cars'), get_main_menu(chat_id))
                return
            
            for car in cars:
                brand_name = car.brand.name if car.brand else ""
                model_name = car.model.name if car.model else ""
                full_brand = f"{brand_name} {model_name}".strip()
                
                caption = t(chat_id, 'car_info').format(
                    title=car.title,
                    price=car.price_usd,
                    mileage=car.mileage_km,
                    brand=full_brand,
                    year=car.year,
                    fuel=car.fuel_type or 'Не указано',
                    transmission=car.transmission or 'Не указано',
                    color=car.color or 'Не указан',
                    engine=car.engine_capacity or 'Не указан',
                    description=car.description or 'Нет описания'
                )
                
                photo_url = car.photo_url1 or car.photo_url2 or car.photo_url3 or car.photo_url4
                send_photo(chat_id, photo_url, caption, get_order_button(chat_id, car.id))
                
                other_photos = []
                if car.photo_url2:
                    other_photos.append(car.photo_url2)
                if car.photo_url3:
                    other_photos.append(car.photo_url3)
                if car.photo_url4:
                    other_photos.append(car.photo_url4)
                
                for photo in other_photos:
                    send_photo(chat_id, photo, "")
                    
    except Exception as e:
        logger.error(f"Ошибка показа авто по марке: {e}")
        send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def show_managers(chat_id):
    with app.app_context():
        managers = Manager.query.filter_by(is_active=True).all()
        
        if not managers:
            managers_text = "👨‍💼 Мухаммед\n📞 +996 555 123 456\n📧 info@suvtekin.kg"
        else:
            managers_text = ""
            for manager in managers:
                managers_text += f"👨‍💼 *{manager.name}*\n"
                if manager.telegram_username:
                    managers_text += f"📞 @{manager.telegram_username}\n"
                if manager.phone:
                    managers_text += f"📱 {manager.phone}\n"
                if manager.email:
                    managers_text += f"📧 {manager.email}\n"
                managers_text += "\n"
    
    message = t(chat_id, 'managers').format(managers=managers_text.strip())
    send_message(chat_id, message, get_main_menu(chat_id))

def start_sell_car(chat_id):
    user_states[chat_id] = {'action': 'sell_car', 'step': 'brand'}
    user_data[chat_id] = {}
    send_message(chat_id, t(chat_id, 'choose_brand_sell'), get_brand_menu(chat_id, 'sell'))

def start_order(chat_id, car_id):
    user_states[chat_id] = {'action': 'order', 'car_id': car_id}
    send_message(chat_id, t(chat_id, 'order_phone'), get_cancel_menu(chat_id))

def complete_order(chat_id, car_id, phone, username, first_name):
    with app.app_context():
        try:
            car = Car.query.get(car_id)
            if car:
                order = Order(
                    car_id=car.id,
                    telegram_user_id=str(chat_id),
                    telegram_username=username or '',
                    telegram_first_name=first_name or '',
                    full_name=first_name or '',
                    phone=phone,
                    status='new'
                )
                db.session.add(order)
                db.session.commit()
                
                admin_msg = f"📥 НОВЫЙ ЗАКАЗ!\n\nАвто: {car.title}\nЦена: ${car.price_usd:,.0f}\nКлиент: @{username or 'нет'}\nТелефон: {phone}\nID: {chat_id}"
                if TELEGRAM_ADMIN_ID:
                    send_message(TELEGRAM_ADMIN_ID, admin_msg)
            
            send_message(chat_id, t(chat_id, 'order_success'), get_main_menu(chat_id))
            user_states.pop(chat_id, None)
        except Exception as e:
            logger.error(f"Ошибка создания заказа: {e}")
            send_message(chat_id, t(chat_id, 'error'), get_main_menu(chat_id))

def complete_sell(chat_id, username, first_name):
    data = user_data.get(chat_id, {})
    
    with app.app_context():
        try:
            sell_request = SellRequest(
                telegram_user_id=str(chat_id),
                telegram_username=username or '',
                telegram_first_name=first_name or '',
                car_brand=data.get('brand', ''),
                car_model=data.get('model', ''),
                car_year=data.get('year'),
                car_mileage=data.get('mileage'),
                car_price=data.get('price'),
                car_description=data.get('description', ''),
                phone=data.get('phone', ''),
                status='new'
            )
            db.session.add(sell_request)
            db.session.commit()
            
            admin_msg = f"""💰 НОВАЯ ЗАЯВКА НА ПРОДАЖУ!

📱 Телеграм: @{username or 'нет'}
👤 Имя: {first_name or 'нет'}
🆔 ID: {chat_id}

🚗 Автомобиль:
Марка: {data.get('brand', 'не указана')}
Модель: {data.get('model', 'не указана')}
Год: {data.get('year', 'не указан')}
Пробег: {data.get('mileage', 'не указан')} км
Цена: ${data.get('price', 0):,.0f}

📝 Описание состояния:
{data.get('description', 'не указано')}

📞 Телефон: {data.get('phone', 'не указан')}"""
            
            if TELEGRAM_ADMIN_ID:
                send_message(TELEGRAM_ADMIN_ID, admin_msg)
        except Exception as e:
            logger.error(f"Ошибка создания заявки: {e}")
    
    send_message(chat_id, t(chat_id, 'sell_car_success'), get_main_menu(chat_id))
    user_states.pop(chat_id, None)
    user_data.pop(chat_id, None)

# Функция для настройки вебхука
def setup_webhook_on_startup():
    try:
        render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://suvtekin.onrender.com')
        
        webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
        
        response = requests.get(f"{BASE_URL}/setWebhook?url={webhook_url}")
        
        if response.status_code == 200:
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка установки вебхука: {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка настройки вебхука: {e}")

# Запускаем настройку вебхука при старте
setup_webhook_on_startup()

# Роуты
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('✅ Успешный вход!', 'success')
            return redirect(url_for('admin.index'))
        else:
            flash('❌ Неверное имя пользователя или пароль', 'danger')
    
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>Вход - Suvtekin Auto</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; }
        .login-container { background: rgba(255, 255, 255, 0.95); border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); padding: 40px; max-width: 400px; width: 100%; }
        .logo { font-size: 3rem; color: #007bff; margin-bottom: 20px; }
        .btn-login { background: linear-gradient(90deg, #007bff, #00d4ff); color: white; border: none; padding: 12px; border-radius: 10px; font-weight: bold; }
        .btn-login:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(0,123,255,0.3); }
    </style>
</head>
<body>
    <div class="container d-flex justify-content-center">
        <div class="login-container">
            <div class="text-center">
                <div class="logo">
                    <i class="fas fa-car"></i>
                </div>
                <h2 class="mb-3">🚗 Suvtekin Auto</h2>
                <p class="text-muted mb-4">Панель управления автосалоном</p>
                
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show">
                                {{ message }}
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}
                
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Логин</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="fas fa-user"></i></span>
                            <input type="text" class="form-control" name="username" value="muha" required>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <label class="form-label">Пароль</label>
                        <div class="input-group">
                            <span class="input-group-text"><i class="fas fa-lock"></i></span>
                            <input type="password" class="form-control" name="password" value="muhamed" required>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-login w-100">
                        <i class="fas fa-sign-in-alt me-2"></i> Войти в систему
                    </button>
                </form>
                
                <div class="mt-4 p-3 bg-light rounded">
                    <small class="text-muted"><strong>Тестовые данные:</strong></small><br>
                    <small>Логин: <strong>muha</strong></small><br>
                    <small>Пароль: <strong>muhamed</strong></small>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
    '''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('✅ Вы вышли из системы', 'success')
    return redirect(url_for('login'))

# Страница проверки
@app.route('/test')
def test():
    cars_count = Car.query.count()
    brands_count = Brand.query.count()
    models_count = CarModel.query.count()
    managers_count = Manager.query.count()
    new_orders = Order.query.filter_by(status='new').count()
    new_sell_requests = SellRequest.query.filter_by(status='new').count()
    
    return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Suvtekin Auto - Статус</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
        .status-card {{ background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        .stat-icon {{ font-size: 2.5rem; margin-bottom: 15px; }}
        .btn-dashboard {{ background: linear-gradient(90deg, #007bff, #00d4ff); color: white; border: none; padding: 12px 30px; border-radius: 50px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="status-card text-center">
            <h1 class="mb-4">🚗 Suvtekin Auto - Статус системы</h1>
            
            <div class="row">
                <div class="col-md-3 mb-4">
                    <div class="p-3 border rounded">
                        <div class="stat-icon text-primary">
                            <i class="fas fa-car"></i>
                        </div>
                        <h3>{cars_count}</h3>
                        <p class="text-muted">Автомобили</p>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="p-3 border rounded">
                        <div class="stat-icon text-success">
                            <i class="fas fa-copyright"></i>
                        </div>
                        <h3>{brands_count}</h3>
                        <p class="text-muted">Бренды</p>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="p-3 border rounded">
                        <div class="stat-icon text-warning">
                            <i class="fas fa-list"></i>
                        </div>
                        <h3>{models_count}</h3>
                        <p class="text-muted">Модели</p>
                    </div>
                </div>
                <div class="col-md-3 mb-4">
                    <div class="p-3 border rounded">
                        <div class="stat-icon text-info">
                            <i class="fas fa-users"></i>
                        </div>
                        <h3>{managers_count}</h3>
                        <p class="text-muted">Менеджеры</p>
                    </div>
                </div>
            </div>
            
            <div class="row mt-3">
                <div class="col-md-6 mb-3">
                    <div class="p-3 border rounded bg-warning bg-opacity-10">
                        <div class="stat-icon text-warning">
                            <i class="fas fa-shopping-cart"></i>
                        </div>
                        <h3>{new_orders}</h3>
                        <p class="text-muted">Новых заказов</p>
                    </div>
                </div>
                <div class="col-md-6 mb-3">
                    <div class="p-3 border rounded bg-info bg-opacity-10">
                        <div class="stat-icon text-info">
                            <i class="fas fa-money-bill-wave"></i>
                        </div>
                        <h3>{new_sell_requests}</h3>
                        <p class="text-muted">Новых заявок на продажу</p>
                    </div>
                </div>
            </div>
            
            <div class="mt-4">
                <a href="/admin" class="btn btn-dashboard me-2">
                    <i class="fas fa-tachometer-alt me-2"></i> Перейти в админку
                </a>
                <a href="/admin/quick-add" class="btn btn-success me-2">
                    <i class="fas fa-plus-circle me-2"></i> Быстрое добавление
                </a>
                <a href="/login" class="btn btn-secondary">
                    <i class="fas fa-sign-in-alt me-2"></i> Войти
                </a>
            </div>
            
            <div class="mt-4 p-3 bg-light rounded">
                <h5>🤖 Telegram бот: @suvtekinn_bot</h5>
                <p>1. Откройте Telegram</p>
                <p>2. Найдите бота: <strong>@suvtekinn_bot</strong></p>
                <p>3. Напишите: <code>/start</code> - выберите язык</p>
                <p>4. Используйте кнопки для навигации</p>
            </div>
        </div>
    </div>
</body>
</html>
    '''

@app.route('/health')
def health():
    return 'OK'

# Ручная настройка вебхука
@app.route('/setup-webhook')
def manual_setup_webhook():
    try:
        render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://suvtekin.onrender.com')
        webhook_url = f"{render_url}/webhook/{TELEGRAM_TOKEN}"
        
        response = requests.get(f"{BASE_URL}/setWebhook?url={webhook_url}")
        
        if response.status_code == 200:
            return f"✅ Вебхук установлен: {webhook_url}<br><br>Ответ Telegram: {response.text}"
        else:
            return f"❌ Ошибка установки вебхука: {response.text}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Запуск Suvtekin Auto на порту {port}")
    logger.info(f"🌐 Адрес: http://localhost:{port}")
    logger.info(f"🔗 Админка: http://localhost:{port}/admin")
    logger.info(f"🔗 Быстрое добавление: http://localhost:{port}/admin/quick-add")
    logger.info(f"🔑 Логин: muha, Пароль: muhamed")
    logger.info(f"🤖 Telegram бот: @suvtekinn_bot")
    
    # Запускаем Flask
    app.run(host='0.0.0.0', port=port, debug=False)