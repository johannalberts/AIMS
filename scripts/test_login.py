"""Test learner user authentication."""
import sys
sys.path.insert(0, '/app')

from app.database import engine
from sqlmodel import Session, select
from app.models import User

with Session(engine) as session:
    user = session.exec(select(User).where(User.email == 'learner@aims.com')).first()
    if user:
        print(f'✅ User found: {user.email}, {user.username}, active={user.is_active}')
        print(f'Password hash length: {len(user.hashed_password)}')
        print(f'Hash starts with: {user.hashed_password[:10]}')
        
        # Test password verification
        result = user.verify_password('learner123')
        print(f'Password verification for "learner123": {result}')
        
        # Test wrong password
        wrong = user.verify_password('wrongpassword')
        print(f'Password verification for "wrongpassword": {wrong}')
    else:
        print('❌ User not found')
