import os
import logging
import json
import requests
from datetime import datetime
from flask import Flask, request, redirect, url_for, flash, jsonify, render_template_string
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash, check_password_hash
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
app.config['SECRET_KEY'] = 'suvtekin-auto-secret-key-2024-muha-muhamed'

# Telegram конфигурация
TELEGRAM_TOKEN = '8586126815:AAHAGyah7Oz-8mHzUcFvRcHV3Dsug3sPT4g'
TELEGRAM_ADMIN_ID = '6349730260'
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Конфигурация базы данных - используем SQLite для простоты
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'cars.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализируем базу данных
db = SQLAlchemy(app)

# Инициализируем Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
        return f'{self.brand.name} {self.name}' if self.brand else self.name

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

# Функция загрузки пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создаем все таблицы при запуске
with app.app_context():
    db.create_all()
    
    # Создаем администратора если нет
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
        logger.info("✅ Администратор создан: admin / admin123")
    
    # Создаем тестовые бренды если нет
    if Brand.query.count() == 0:
        brands = ['Toyota', 'Honda', 'BMW', 'Mercedes', 'Audi', 'Ford', 'Chevrolet']
        for brand_name in brands:
            brand = Brand(name=brand_name)
            db.session.add(brand)
        db.session.commit()
        logger.info("✅ Тестовые бренды созданы")
    
    # Создаем ценовые категории если нет
    if PriceCategory.query.count() == 0:
        categories = [
            ('0-3000$', 0, 3000),
            ('3000-6000$', 3000, 6000),
            ('6000-10000$', 6000, 10000),
            ('10000-20000$', 10000, 20000),
            ('20000+$', 20000, 1000000)
        ]
        for name, min_p, max_p in categories:
            category = PriceCategory(name=name, min_price_usd=min_p, max_price_usd=max_p)
            db.session.add(category)
        db.session.commit()
        logger.info("✅ Ценовые категории созданы")

# Кастомная ModelView для админки
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login'))

# Настройка админки
admin = Admin(app, name='Suvtekin Auto', template_mode='bootstrap3')

# Добавляем модели в админку
admin.add_view(SecureModelView(User, db.session, name='Пользователи'))
admin.add_view(SecureModelView(Brand, db.session, name='Бренды'))
admin.add_view(SecureModelView(CarModel, db.session, name='Модели'))
admin.add_view(SecureModelView(PriceCategory, db.session, name='Категории цен'))
admin.add_view(SecureModelView(Car, db.session, name='Автомобили'))
admin.add_view(SecureModelView(Order, db.session, name='Заказы'))
admin.add_view(SecureModelView(SellRequest, db.session, name='Заявки на продажу'))

# Telegram бот функции
def send_telegram_message(chat_id, text, reply_markup=None):
    """Отправка сообщения в Telegram"""
    url = f"{BASE_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")
        return None

def send_car_to_telegram(car, chat_id=None):
    """Отправка информации об авто в Telegram"""
    if not chat_id:
        chat_id = TELEGRAM_ADMIN_ID
    
    message = f"""
🚗 <b>НОВЫЙ АВТОМОБИЛЬ!</b>

<b>Марка:</b> {car.brand.name if car.brand else 'Не указана'}
<b>Модель:</b> {car.model.name if car.model else 'Не указана'}
<b>Год:</b> {car.year or 'Не указан'}
<b>Цена:</b> ${car.price_usd:,.0f}
<b>Пробег:</b> {car.mileage_km or 'Не указан'} км

<b>Описание:</b>
{car.description[:200]}...

<b>Просмотреть в каталоге:</b> /cars
"""
    
    if car.photo_url1:
        # Отправляем фото с описанием
        url = f"{BASE_URL}/sendPhoto"
        payload = {
            'chat_id': chat_id,
            'photo': car.photo_url1,
            'caption': message,
            'parse_mode': 'HTML'
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except:
            # Если фото не отправляется, отправляем просто текст
            send_telegram_message(chat_id, message)
    else:
        send_telegram_message(chat_id, message)

# Вебхук для Telegram
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '')
            
            if text == '/start':
                send_welcome_message(chat_id)
            elif text == '/cars':
                send_cars_list(chat_id)
            elif text == '/help':
                send_help_message(chat_id)
            
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Ошибка в вебхуке: {e}")
        return jsonify({'ok': False})

def send_welcome_message(chat_id):
    """Отправка приветственного сообщения"""
    message = """
🚗 <b>Добро пожаловать в Suvtekin Auto!</b>

Мы предлагаем лучшие автомобили по выгодным ценам.

<b>Доступные команды:</b>
/cars - Посмотреть автомобили
/help - Помощь

<b>Наши услуги:</b>
• Покупка автомобилей
• Продажа вашего авто
• Консультация менеджера

<b>Контакты:</b>
📞 +996 555 123 456
📧 info@suvtekin.kg
"""
    send_telegram_message(chat_id, message, {
        'keyboard': [
            [{'text': '🚗 Посмотреть авто'}],
            [{'text': '💰 Продать авто'}, {'text': '📞 Контакты'}],
            [{'text': 'ℹ️ Помощь'}]
        ],
        'resize_keyboard': True
    })

def send_cars_list(chat_id):
    """Отправка списка автомобилей"""
    with app.app_context():
        cars = Car.query.filter_by(is_active=True).order_by(Car.created_at.desc()).limit(5).all()
        
        if not cars:
            send_telegram_message(chat_id, "🚗 На данный момент нет доступных автомобилей.")
            return
        
        for car in cars:
            message = f"""
🚗 <b>{car.title}</b>

💰 <b>Цена:</b> ${car.price_usd:,.0f}
📏 <b>Пробег:</b> {car.mileage_km or 'Не указан'} км
🏭 <b>Марка:</b> {car.brand.name if car.brand else 'Не указана'}
📅 <b>Год:</b> {car.year or 'Не указан'}
⛽ <b>Топливо:</b> {car.fuel_type or 'Не указано'}
⚙️ <b>КПП:</b> {car.transmission or 'Не указано'}

{car.description[:150]}...
"""
            
            # Создаем inline-кнопку для заказа
            keyboard = {
                'inline_keyboard': [[
                    {'text': '🛒 Заказать', 'callback_data': f'order_{car.id}'},
                    {'text': 'ℹ️ Подробнее', 'url': f'https://suvtekin.onrender.com/car/{car.id}'}
                ]]
            }
            
            if car.photo_url1:
                # Отправляем фото
                url = f"{BASE_URL}/sendPhoto"
                payload = {
                    'chat_id': chat_id,
                    'photo': car.photo_url1,
                    'caption': message,
                    'parse_mode': 'HTML',
                    'reply_markup': json.dumps(keyboard)
                }
                try:
                    requests.post(url, json=payload, timeout=10)
                except:
                    send_telegram_message(chat_id, message, keyboard)
            else:
                send_telegram_message(chat_id, message, keyboard)

def send_help_message(chat_id):
    """Отправка помощи"""
    message = """
ℹ️ <b>Помощь по боту Suvtekin Auto</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/cars - Посмотреть доступные автомобили
/help - Эта справка

<b>Как заказать авто:</b>
1. Нажмите "🚗 Посмотреть авто"
2. Выберите понравившийся автомобиль
3. Нажмите "🛒 Заказать"
4. Оставьте свои контакты

<b>Продать свой автомобиль:</b>
Нажмите "💰 Продать авто" и следуйте инструкциям.

<b>Контакты:</b>
📞 +996 555 123 456
📧 info@suvtekin.kg
🕒 Работаем: 9:00 - 19:00
"""
    send_telegram_message(chat_id, message)

# Обработчик callback запросов от кнопок
@app.route('/callback', methods=['POST'])
def telegram_callback():
    try:
        data = request.get_json()
        
        if 'callback_query' in data:
            callback = data['callback_query']
            chat_id = callback['message']['chat']['id']
            data_str = callback['data']
            
            if data_str.startswith('order_'):
                car_id = int(data_str.split('_')[1])
                start_order_process(chat_id, car_id)
            
            # Отвечаем на callback
            url = f"{BASE_URL}/answerCallbackQuery"
            requests.post(url, json={'callback_query_id': callback['id']})
        
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")
        return jsonify({'ok': False})

def start_order_process(chat_id, car_id):
    """Начало процесса заказа"""
    with app.app_context():
        car = Car.query.get(car_id)
        if car:
            message = f"""
🛒 <b>Заказ автомобиля</b>

Вы выбрали: <b>{car.title}</b>
Цена: <b>${car.price_usd:,.0f}</b>

<b>Для оформления заказа, пожалуйста, отправьте:</b>
1. Ваше имя
2. Номер телефона
3. Удобное время для связи

<b>Пример:</b>
Имя: Азамат
Телефон: +996 555 123 456
Время: после 15:00
"""
            
            # Сохраняем состояние пользователя (в реальном проекте используйте БД или Redis)
            # Здесь для простоты просто отправляем сообщение
            
            send_telegram_message(chat_id, message, {
                'keyboard': [[{'text': '❌ Отмена'}]],
                'resize_keyboard': True,
                'one_time_keyboard': True
            })

# Веб-интерфейс
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
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
        <style>
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; }
            .login-box { background: white; border-radius: 20px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 400px; width: 100%; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="login-box">
                        <h2 class="text-center mb-4">🚗 Suvtekin Auto</h2>
                        <p class="text-center text-muted mb-4">Панель управления</p>
                        
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }}">{{ message }}</div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label class="form-label">Логин</label>
                                <input type="text" class="form-control" name="username" value="admin" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Пароль</label>
                                <input type="password" class="form-control" name="password" value="admin123" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Войти</button>
                        </form>
                        
                        <div class="mt-4 text-center">
                            <small class="text-muted">Тестовые данные: admin / admin123</small>
                        </div>
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

# Страница быстрого добавления авто
@app.route('/add-car', methods=['GET', 'POST'])
@login_required
def add_car():
    if request.method == 'POST':
        try:
            # Создаем новый автомобиль
            car = Car(
                title=request.form.get('title'),
                description=request.form.get('description', ''),
                price_usd=float(request.form.get('price_usd', 0)),
                year=int(request.form.get('year', 0)) if request.form.get('year') else None,
                mileage_km=int(request.form.get('mileage_km', 0)) if request.form.get('mileage_km') else None,
                fuel_type=request.form.get('fuel_type', ''),
                transmission=request.form.get('transmission', ''),
                color=request.form.get('color', ''),
                engine_capacity=float(request.form.get('engine_capacity', 0)) if request.form.get('engine_capacity') else None,
                photo_url1=request.form.get('photo_url1', ''),
                photo_url2=request.form.get('photo_url2', ''),
                photo_url3=request.form.get('photo_url3', ''),
                photo_url4=request.form.get('photo_url4', ''),
                is_active=True
            )
            
            # Находим или создаем бренд
            brand_name = request.form.get('brand_name', '').strip()
            if brand_name:
                brand = Brand.query.filter_by(name=brand_name).first()
                if not brand:
                    brand = Brand(name=brand_name)
                    db.session.add(brand)
                    db.session.flush()
                car.brand_id = brand.id
            
            # Находим или создаем модель
            model_name = request.form.get('model_name', '').strip()
            if model_name and car.brand_id:
                model = CarModel.query.filter_by(name=model_name, brand_id=car.brand_id).first()
                if not model:
                    model = CarModel(name=model_name, brand_id=car.brand_id)
                    db.session.add(model)
                    db.session.flush()
                car.model_id = model.id
            
            db.session.add(car)
            db.session.commit()
            
            flash(f'✅ Автомобиль "{car.title}" добавлен!', 'success')
            
            # Отправляем уведомление в Telegram
            try:
                send_car_to_telegram(car)
                flash('✅ Уведомление отправлено в Telegram!', 'success')
            except Exception as e:
                logger.error(f"Ошибка отправки в Telegram: {e}")
                flash('⚠️ Автомобиль добавлен, но не отправлен в Telegram', 'warning')
            
            return redirect(url_for('add_car'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка добавления авто: {e}")
            flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    # Получаем бренды для выпадающего списка
    brands = Brand.query.all()
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Добавить авто - Suvtekin Auto</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #f8f9fa; padding: 20px; }
            .container { max-width: 800px; }
            .card { border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .btn-primary { background: linear-gradient(90deg, #007bff, #00d4ff); border: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <nav class="navbar navbar-light bg-white rounded mb-4">
                <div class="container-fluid">
                    <a class="navbar-brand" href="#">
                        🚗 <b>Suvtekin Auto</b>
                    </a>
                    <div>
                        <a href="/admin" class="btn btn-outline-primary btn-sm me-2">Админка</a>
                        <a href="/logout" class="btn btn-outline-danger btn-sm">Выйти</a>
                    </div>
                </div>
            </nav>
            
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">➕ Добавить новый автомобиль</h4>
                </div>
                <div class="card-body">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ category }}">{{ message }}</div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <form method="POST">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Название автомобиля *</label>
                                <input type="text" class="form-control" name="title" required 
                                       placeholder="Toyota Camry 2020">
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Цена ($) *</label>
                                <input type="number" step="0.01" class="form-control" name="price_usd" required 
                                       placeholder="15000">
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Бренд *</label>
                                <input type="text" class="form-control" name="brand_name" required 
                                       placeholder="Toyota" list="brands-list">
                                <datalist id="brands-list">
                                    {% for brand in brands %}
                                    <option value="{{ brand.name }}">
                                    {% endfor %}
                                </datalist>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Модель *</label>
                                <input type="text" class="form-control" name="model_name" required 
                                       placeholder="Camry">
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Год выпуска</label>
                                <input type="number" class="form-control" name="year" 
                                       placeholder="2020" min="1900" max="2024">
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Пробег (км)</label>
                                <input type="number" class="form-control" name="mileage_km" 
                                       placeholder="50000">
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="form-label">Объем двигателя (л)</label>
                                <input type="number" step="0.1" class="form-control" name="engine_capacity" 
                                       placeholder="2.0">
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Тип топлива</label>
                                <select class="form-control" name="fuel_type">
                                    <option value="">Выберите...</option>
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
                                    <option value="">Выберите...</option>
                                    <option value="Автомат">Автомат</option>
                                    <option value="Механика">Механика</option>
                                    <option value="Вариатор">Вариатор</option>
                                </select>
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="form-label">Цвет</label>
                                <input type="text" class="form-control" name="color" placeholder="Черный">
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Описание</label>
                            <textarea class="form-control" name="description" rows="3" 
                                      placeholder="Отличное состояние, полная комплектация..."></textarea>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Фотографии (URL)</label>
                            <div class="row">
                                <div class="col-md-6 mb-2">
                                    <input type="url" class="form-control" name="photo_url1" 
                                           placeholder="https://example.com/photo1.jpg">
                                </div>
                                <div class="col-md-6 mb-2">
                                    <input type="url" class="form-control" name="photo_url2" 
                                           placeholder="https://example.com/photo2.jpg">
                                </div>
                                <div class="col-md-6 mb-2">
                                    <input type="url" class="form-control" name="photo_url3" 
                                           placeholder="https://example.com/photo3.jpg">
                                </div>
                                <div class="col-md-6 mb-2">
                                    <input type="url" class="form-control" name="photo_url4" 
                                           placeholder="https://example.com/photo4.jpg">
                                </div>
                            </div>
                            <small class="text-muted">Первая фотография будет основной</small>
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <button type="submit" class="btn btn-primary btn-lg">
                                ✅ Добавить автомобиль
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <div class="mt-4">
                <div class="card">
                    <div class="card-body">
                        <h5>📱 Интеграция с Telegram</h5>
                        <p>После добавления автомобиля, уведомление автоматически отправится в Telegram-бот.</p>
                        <p><b>Telegram бот:</b> @suvtekinn_bot</p>
                        <p><b>Для тестирования:</b></p>
                        <ol>
                            <li>Откройте Telegram</li>
                            <li>Найдите бота: <code>@suvtekinn_bot</code></li>
                            <li>Напишите <code>/start</code></li>
                            <li>Добавьте авто здесь → получите уведомление в боте</li>
                        </ol>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Автозаполнение года текущим
            document.addEventListener('DOMContentLoaded', function() {
                const yearInput = document.querySelector('input[name="year"]');
                if (yearInput && !yearInput.value) {
                    yearInput.value = new Date().getFullYear();
                }
            });
        </script>
    </body>
    </html>
    '''

# Страница статистики
@app.route('/dashboard')
@login_required
def dashboard():
    total_cars = Car.query.count()
    active_cars = Car.query.filter_by(is_active=True).count()
    new_orders = Order.query.filter_by(status='new').count()
    new_sell_requests = SellRequest.query.filter_by(status='new').count()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Дашборд - Suvtekin Auto</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            body {{ background: #f8f9fa; padding: 20px; }}
            .stats-card {{ background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .stat-icon {{ font-size: 2.5rem; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <nav class="navbar navbar-light bg-white rounded mb-4">
                <div class="container-fluid">
                    <a class="navbar-brand" href="#">
                        📊 <b>Дашборд Suvtekin Auto</b>
                    </a>
                    <div>
                        <a href="/add-car" class="btn btn-primary btn-sm me-2">➕ Добавить авто</a>
                        <a href="/admin" class="btn btn-outline-primary btn-sm me-2">Админка</a>
                        <a href="/logout" class="btn btn-outline-danger btn-sm">Выйти</a>
                    </div>
                </div>
            </nav>
            
            <div class="row">
                <div class="col-md-3">
                    <div class="stats-card text-center">
                        <div class="stat-icon text-primary">
                            <i class="fas fa-car"></i>
                        </div>
                        <h3>{total_cars}</h3>
                        <p class="text-muted">Всего авто</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stats-card text-center">
                        <div class="stat-icon text-success">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <h3>{active_cars}</h3>
                        <p class="text-muted">Активных авто</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stats-card text-center">
                        <div class="stat-icon text-warning">
                            <i class="fas fa-shopping-cart"></i>
                        </div>
                        <h3>{new_orders}</h3>
                        <p class="text-muted">Новых заказов</p>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stats-card text-center">
                        <div class="stat-icon text-info">
                            <i class="fas fa-money-bill-wave"></i>
                        </div>
                        <h3>{new_sell_requests}</h3>
                        <p class="text-muted">Заявок на продажу</p>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">⚡ Быстрые действия</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-3 mb-3">
                                    <a href="/add-car" class="btn btn-primary w-100">
                                        <i class="fas fa-plus-circle me-2"></i>Добавить авто
                                    </a>
                                </div>
                                <div class="col-md-3 mb-3">
                                    <a href="/admin/car" class="btn btn-success w-100">
                                        <i class="fas fa-edit me-2"></i>Управление авто
                                    </a>
                                </div>
                                <div class="col-md-3 mb-3">
                                    <a href="/admin/order" class="btn btn-warning w-100">
                                        <i class="fas fa-shopping-cart me-2"></i>Заказы
                                    </a>
                                </div>
                                <div class="col-md-3 mb-3">
                                    <a href="https://t.me/suvtekinn_bot" target="_blank" class="btn btn-info w-100">
                                        <i class="fab fa-telegram me-2"></i>Telegram бот
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

# API для проверки статуса
@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'ok',
        'service': 'Suvtekin Auto',
        'cars_count': Car.query.count(),
        'orders_count': Order.query.count(),
        'telegram_bot': 'active' if TELEGRAM_TOKEN else 'inactive'
    })

# Настройка вебхука при запуске
def setup_webhook():
    if TELEGRAM_TOKEN:
        try:
            render_url = 'https://suvtekin.onrender.com'
            webhook_url = f"{render_url}/webhook"
            
            # Удаляем старый вебхук
            requests.get(f"{BASE_URL}/deleteWebhook")
            
            # Устанавливаем новый вебхук
            response = requests.post(
                f"{BASE_URL}/setWebhook",
                json={'url': webhook_url}
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Вебхук установлен: {webhook_url}")
            else:
                logger.error(f"❌ Ошибка установки вебхука: {response.text}")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки вебхука: {e}")
    else:
        logger.warning("⚠️ TELEGRAM_TOKEN не установлен, бот не будет работать")

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        # Настраиваем вебхук
        setup_webhook()
        
        logger.info("=" * 50)
        logger.info("🚗 Suvtekin Auto запущен!")
        logger.info("🌐 Сайт: https://suvtekin.onrender.com")
        logger.info("🔑 Логин: admin / admin123")
        logger.info("🤖 Telegram бот: @suvtekinn_bot")
        logger.info("=" * 50)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
