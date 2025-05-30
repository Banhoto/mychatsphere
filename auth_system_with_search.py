from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import bcrypt
import smtplib
import random
import string
from email.mime.text import MIMEText
import jwt
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Замени на свой секретный ключ
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6), nullable=True)

# Создание базы данных
with app.app_context():
    db.create_all()

# Функция для отправки email с кодом
def send_verification_email(email, code):
    sender = "your_email@example.com"  # Замени на свой email
    password = "your_app_password"  # Используй пароль приложения для Gmail
    msg = MIMEText(f"Your verification code is: {code}")
    msg['Subject'] = 'Verify Your Email'
    msg['From'] = sender
    msg['To'] = email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, email, msg.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Генерация случайного кода
def generate_code():
    return ''.join(random.choices(string.digits, k=6))

# Регистрация пользователя
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    nickname = data.get('nickname')
    password = data.get('password')

    if not email or not nickname or not password:
        return jsonify({'error': 'Missing email, nickname, or password'}), 400

    if User.query.filter_by(email=email).first() or User.query.filter_by(nickname=nickname).first():
        return jsonify({'error': 'Email or nickname already exists'}), 409

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    verification_code = generate_code()

    new_user = User(email=email, nickname=nickname, password=hashed_password, verification_code=verification_code)
    db.session.add(new_user)
    db.session.commit()

    if send_verification_email(email, verification_code):
        return jsonify({'message': 'User registered. Check your email for verification code.', 'user_id': new_user.id}), 201
    else:
        db.session.delete(new_user)
        db.session.commit()
        return jsonify({'error': 'Failed to send verification email'}), 500

# Проверка кода
@app.route('/verify', methods=['POST'])
def verify():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.is_verified:
        return jsonify({'error': 'User already verified'}), 400

    if user.verification_code == code:
        user.is_verified = True
        user.verification_code = None
        db.session.commit()
        return jsonify({'message': 'Email verified successfully'}), 200
    else:
        return jsonify({'error': 'Invalid verification code'}), 400

# Авторизация
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.is_verified:
        return jsonify({'error': 'Email not verified'}), 403

    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'nickname': user.nickname, 'user_id': user.id}), 200

# Поиск пользователя по ID или никнейму
@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query')  # Может быть ID или никнейм

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    # Проверяем, является ли query числом (ID)
    try:
        user_id = int(query)
        user = User.query.filter_by(id=user_id).first()
    except ValueError:
        # Если не число, ищем по никнейму
        user = User.query.filter_by(nickname=query).first()

    if user:
        return jsonify({'user_id': user.id, 'nickname': user.nickname, 'email': user.email if user.is_verified else 'Not verified'}), 200
    else:
        return jsonify({'error': 'User not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)