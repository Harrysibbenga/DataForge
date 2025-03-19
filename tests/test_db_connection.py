"""
tests/test_db_connection.py - Test database connection
"""
import unittest
import os
import sys
from sqlalchemy import create_engine, text, Column, String, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import get_settings

class TestDatabaseConnection(unittest.TestCase):
    """Test cases for database connection"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.settings = get_settings()
        self.engine = create_engine(str(self.settings.DATABASE_URL))
        
        # Create a session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create a base class for declarative models
        self.Base = declarative_base()
        
        # Define a simple test model
        class TestModel(self.Base):
            __tablename__ = "test_connection_table"
            id = Column(String, primary_key=True)
            
        self.TestModel = TestModel
        
    def tearDown(self):
        """Clean up test fixtures"""
        # Drop the test table if it exists
        inspector = inspect(self.engine)
        if inspector.has_table(self.TestModel.__tablename__):
            self.TestModel.__table__.drop(self.engine)
    
    def test_basic_connection(self):
        """Test basic database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                # Check if we got a result
                self.assertEqual(result.scalar(), 1)
        except Exception as e:
            self.fail(f"Database connection failed: {str(e)}")
    
    def test_create_table(self):
        """Test ability to create and use tables"""
        try:
            # Create the table
            self.Base.metadata.create_all(self.engine, tables=[self.TestModel.__table__])
            
            # Verify the table exists
            inspector = inspect(self.engine)
            self.assertTrue(
                inspector.has_table(self.TestModel.__tablename__),
                f"Table {self.TestModel.__tablename__} was not created"
            )
            
            # Test inserting and querying data
            test_id = "test1"
            
            with self.SessionLocal() as session:
                # Insert a record
                test_obj = self.TestModel(id=test_id)
                session.add(test_obj)
                session.commit()
                
                # Query the record
                result = session.query(self.TestModel).filter_by(id=test_id).first()
                self.assertIsNotNone(result, "Could not retrieve test record")
                self.assertEqual(result.id, test_id, f"Retrieved id {result.id} doesn't match expected {test_id}")
        except Exception as e:
            self.fail(f"Table creation or data manipulation failed: {str(e)}")
    
    def test_database_url_format(self):
        """Test that the database URL has the right format"""
        db_url = str(self.settings.DATABASE_URL)
        
        # Check what type of database we're using
        if db_url.startswith("sqlite"):
            self.assertTrue(
                db_url.startswith("sqlite:///"), 
                f"Invalid SQLite URL format: {db_url}"
            )
        elif db_url.startswith("postgresql"):
            # Check for postgresql://{user}:{pass}@{host}:{port}/{dbname}
            parts = db_url.replace("postgresql://", "").split("@")
            self.assertEqual(
                len(parts), 2, 
                f"Invalid PostgreSQL URL format: {db_url}"
            )
        else:
            self.fail(f"Unsupported database type in URL: {db_url}")

if __name__ == "__main__":
    unittest.main()