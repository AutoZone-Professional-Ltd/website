import os
import json
import re
import requests
import mysql.connector
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from datetime import datetime, date

requests.packages.urllib3.disable_warnings()


class ChatbotLearningSystem:
    """
    Real-time learning system for the chatbot.
    - Stores every Q&A interaction
    - Learns from similar questions
    - Tracks unanswered questions
    - Provides feedback mechanism
    """
    
    def __init__(self):
        self.db_config = {
            "host": "172.18.0.2",
            "port": 3306,
            "user": "erp_root",
            "password": "Autopro2025?",
            "database": "custom_erp"
        }
        self._memory = {}  # In-memory cache for fast access
        self._load_memory()
    
    def _get_connection(self):
        return mysql.connector.connect(**self.db_config)
    
    def _load_memory(self):
        """Load recent learnings into memory for fast access."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_learnings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    question_normalized VARCHAR(500),
                    intent VARCHAR(100),
                    keywords VARCHAR(500),
                    confidence_score FLOAT DEFAULT 1.0,
                    view_count INT DEFAULT 1,
                    helpful_count INT DEFAULT 0,
                    unhelpful_count INT DEFAULT 0,
                    success BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_question_normalized (question_normalized),
                    INDEX idx_keywords (keywords(100)),
                    INDEX idx_success (success)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Create feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_feedback (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    is_helpful BOOLEAN,
                    user_comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_is_helpful (is_helpful)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Create unanswered questions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chatbot_unanswered (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    question TEXT NOT NULL,
                    question_normalized VARCHAR(500),
                    ask_count INT DEFAULT 1,
                    first_asked DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_asked DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_ask_count (ask_count DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            
            # Load successful learnings into memory
            cursor.execute("""
                SELECT question, answer, question_normalized, intent, keywords, confidence_score, COALESCE(view_count, 0) as view_count
                FROM chatbot_learnings 
                WHERE success = TRUE 
                ORDER BY confidence_score DESC, view_count DESC
                LIMIT 500
            """)
            
            for row in cursor.fetchall():
                key = row['question_normalized']
                self._memory[key] = {
                    'question': row['question'],
                    'answer': row['answer'],
                    'intent': row['intent'],
                    'keywords': row['keywords'],
                    'confidence': row['confidence_score'],
                    'views': row['view_count']
                }
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error loading learning memory: {e}")
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for matching."""
        normalized = question.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized).strip()  # Normalize spaces
        return normalized
    
    def _extract_keywords(self, question: str) -> str:
        """Extract keywords from question."""
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'do', 'does', 'did',
                      'what', 'which', 'who', 'how', 'when', 'where', 'why', 'can', 'could',
                      'i', 'you', 'we', 'they', 'it', 'in', 'on', 'at', 'to', 'for', 'of',
                      'and', 'or', 'but', 'my', 'your', 'our', 'this', 'that', 'these', 'those'}
        
        words = re.findall(r'\b[a-z]{3,}\b', question.lower())
        keywords = [w for w in words if w not in stop_words]
        return ','.join(keywords[:10])
    
    def _calculate_similarity(self, q1: str, q2: str) -> float:
        """Calculate similarity between two questions."""
        # Word-based similarity
        words1 = set(q1.lower().split())
        words2 = set(q2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        word_sim = intersection / union if union > 0 else 0
        
        # Sequence similarity
        seq_sim = SequenceMatcher(None, q1.lower(), q2.lower()).ratio()
        
        # Combined score (weighted)
        return (word_sim * 0.6) + (seq_sim * 0.4)
    
    def learn(self, question: str, answer: str, intent: str = None, success: bool = True):
        """Learn from a Q&A interaction."""
        try:
            normalized = self._normalize_question(question)
            keywords = self._extract_keywords(question)
            
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Check if this exact question exists
            cursor.execute(
                "SELECT id, view_count FROM chatbot_learnings WHERE question_normalized = %s",
                (normalized,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute("""
                    UPDATE chatbot_learnings 
                    SET view_count = view_count + 1, 
                        last_used = NOW(),
                        success = COALESCE(%s, success)
                    WHERE id = %s
                """, (success, existing['id']))
            else:
                # Insert new learning
                cursor.execute("""
                    INSERT INTO chatbot_learnings 
                    (question, answer, question_normalized, intent, keywords, success, confidence_score)
                    VALUES (%s, %s, %s, %s, %s, %s, 1.0)
                """, (question, answer, normalized, intent or 'unknown', keywords, success))
            
            # Update memory
            self._memory[normalized] = {
                'question': question,
                'answer': answer,
                'intent': intent,
                'keywords': keywords,
                'confidence': 1.0,
                'views': existing['view_count'] + 1 if existing else 1
            }
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error in learning: {e}")
    
    def record_unanswered(self, question: str):
        """Record a question that couldn't be answered."""
        try:
            normalized = self._normalize_question(question)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute(
                "SELECT id FROM chatbot_unanswered WHERE question_normalized = %s",
                (normalized,)
            )
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute(
                    "UPDATE chatbot_unanswered SET ask_count = ask_count + 1 WHERE id = %s",
                    (existing[0],)
                )
            else:
                cursor.execute("""
                    INSERT INTO chatbot_unanswered (question, question_normalized, ask_count)
                    VALUES (%s, %s, 1)
                """, (question, normalized))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error recording unanswered: {e}")
    
    def find_learned_answer(self, question: str, threshold: float = 0.75) -> Optional[Dict]:
        """Find a previously learned answer for a similar question."""
        normalized = self._normalize_question(question)
        
        # First check exact match in memory
        if normalized in self._memory:
            result = self._memory[normalized].copy()
            result['match_score'] = 1.0  # Exact match
            return result
        
        # Search for similar questions
        best_match = None
        best_score = 0
        
        for learned_normalized, data in self._memory.items():
            score = self._calculate_similarity(normalized, learned_normalized)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = data.copy()
                best_match['match_score'] = score
        
        return best_match
    
    def get_feedback_questions(self) -> List[Dict]:
        """Get frequently asked but unanswered questions for review."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT question, ask_count, first_asked, last_asked
                FROM chatbot_unanswered
                WHERE ask_count >= 3
                ORDER BY ask_count DESC
                LIMIT 50
            """)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
            
        except Exception as e:
            print(f"Error getting feedback questions: {e}")
            return []
    
    def record_feedback(self, question: str, answer: str, is_helpful: bool, comment: str = None):
        """Record user feedback on an answer."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chatbot_feedback (question, answer, is_helpful, user_comment)
                VALUES (%s, %s, %s, %s)
            """, (question, answer, is_helpful, comment))
            
            # Update learning confidence
            normalized = self._normalize_question(question)
            if is_helpful:
                cursor.execute("""
                    UPDATE chatbot_learnings 
                    SET helpful_count = helpful_count + 1,
                        confidence_score = LEAST(confidence_score + 0.1, 1.0)
                    WHERE question_normalized = %s
                """, (normalized,))
            else:
                cursor.execute("""
                    UPDATE chatbot_learnings 
                    SET unhelpful_count = unhelpful_count + 1,
                        confidence_score = GREATEST(confidence_score - 0.05, 0.0)
                    WHERE question_normalized = %s
                """, (normalized,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Error recording feedback: {e}")
    
    def suggest_answers(self, question: str) -> List[Dict]:
        """Suggest potential answers based on learned patterns."""
        try:
            keywords = self._extract_keywords(question).split(',')
            
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Find questions with matching keywords
            conditions = ' OR '.join(['keywords LIKE %s'] * min(len(keywords), 5))
            params = [f'%{k}%' for k in keywords[:5]]
            
            cursor.execute(f"""
                SELECT question, answer, confidence_score, view_count
                FROM chatbot_learnings
                WHERE success = TRUE AND ({conditions})
                ORDER BY confidence_score DESC, view_count DESC
                LIMIT 5
            """, params)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
            
        except Exception as e:
            print(f"Error suggesting answers: {e}")
            return []


class HistoricalData:
    """Access historical invoice data from erp_demo database (201,467 invoices 2020-2026)."""
    
    def __init__(self):
        self.db_config = {
            "host": "172.18.0.2",
            "port": 3306,
            "user": "erp_root",
            "password": "Autopro2025?",
            "database": "custom_erp"
        }
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 300
    
    def _get_connection(self):
        return mysql.connector.connect(**self.db_config)
    
    def _is_cache_valid(self, key):
        if key not in self._cache:
            return False
        if key not in self._cache_time:
            return False
        return (datetime.now() - self._cache_time[key]).total_seconds() < self._cache_ttl
    
    def _set_cache(self, key, value):
        self._cache[key] = value
        self._cache_time[key] = datetime.now()
    
    def get_total_stats(self):
        if self._is_cache_valid("total_stats"):
            return self._cache["total_stats"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_invoices,
                SUM(sales_amount) as total_sales,
                COUNT(DISTINCT party) as total_customers,
                COUNT(DISTINCT brand) as total_brands,
                MIN(invoice_date) as earliest_date,
                MAX(invoice_date) as latest_date
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND party != 'Shortage'
        """)
        stats = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(DISTINCT description) as unique_items FROM erp_pastinvoices WHERE description != ''")
        stats["unique_items"] = cursor.fetchone()["unique_items"]
        
        cursor.close()
        conn.close()
        
        self._set_cache("total_stats", stats)
        return stats
    
    def get_sales_by_brand(self, limit=20):
        if self._is_cache_valid("sales_by_brand"):
            return self._cache["sales_by_brand"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT brand, COUNT(*) as invoice_count, SUM(sales_amount) as total_sales, SUM(item_qty) as total_qty
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND brand IS NOT NULL AND brand != ''
            GROUP BY brand 
            ORDER BY total_sales DESC 
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("sales_by_brand", results)
        return results
    
    def get_sales_by_region(self, limit=20):
        if self._is_cache_valid("sales_by_region"):
            return self._cache["sales_by_region"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT region, COUNT(*) as invoice_count, SUM(sales_amount) as total_sales
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND region IS NOT NULL AND region != ''
            GROUP BY region 
            ORDER BY total_sales DESC 
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("sales_by_region", results)
        return results
    
    def get_sales_by_salesperson(self, limit=20):
        if self._is_cache_valid("sales_by_salesperson"):
            return self._cache["sales_by_salesperson"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT sales_person, COUNT(*) as invoice_count, SUM(sales_amount) as total_sales
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND sales_person IS NOT NULL AND sales_person != '' AND sales_person != 'Shortage'
            GROUP BY sales_person 
            ORDER BY total_sales DESC 
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("sales_by_salesperson", results)
        return results
    
    def get_top_customers(self, limit=15):
        if self._is_cache_valid("top_customers"):
            return self._cache["top_customers"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT party as customer, region, sales_person,
                   COUNT(*) as invoice_count, SUM(sales_amount) as total_sales
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND party IS NOT NULL AND party != '' AND party != 'Shortage'
            GROUP BY party, region, sales_person
            ORDER BY total_sales DESC 
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("top_customers", results)
        return results
    
    def get_top_products(self, limit=20):
        if self._is_cache_valid("top_products"):
            return self._cache["top_products"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT brand, description as product, model, hsn,
                   COUNT(*) as transactions, SUM(item_qty) as total_qty, SUM(sales_amount) as total_sales
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND description IS NOT NULL AND description != ''
            GROUP BY brand, description, model, hsn
            ORDER BY total_qty DESC 
            LIMIT %s
        """, (limit,))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("top_products", results)
        return results
    
    def search_by_model(self, model_query, limit=30):
        """Search for parts compatible with a specific bike model."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Map common model names
        model_map = {
            "bm100ks": "BM100KS", "bm100es": "BM100ES", "bm150": "BM150",
            "ct125": "CT125", "hero": "Hero", "hunk": "Hero-Hunter",
            "hunter": "Hero-Hunter", "destini": "Destini", "xpulse": "Xpulse",
            "bajaj": "Bajaj", "pulsar": "Pulsar", "discover": "Discover",
            "tvs": "TVS", "hlx": "HLX", "apache": "Apache", "victor": "Victor"
        }
        
        search_term = model_query.lower()
        if search_term in model_map:
            search_term = model_map[search_term]
        
        cursor.execute("""
            SELECT description, brand, model, hsn,
                   COUNT(*) as transactions, SUM(item_qty) as total_qty, SUM(sales_amount) as total_sales,
                   AVG(sales_amount/item_qty) as avg_price
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND item_qty > 0 AND model LIKE %s
            GROUP BY description, brand, model, hsn
            ORDER BY total_qty DESC 
            LIMIT %s
        """, (f"%{search_term}%", limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return results
    
    def get_model_list(self):
        """Get list of all motorcycle models."""
        if self._is_cache_valid("model_list"):
            return self._cache["model_list"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT DISTINCT model FROM erp_pastinvoices 
            WHERE model IS NOT NULL AND model != ''
            ORDER BY model
        """)
        results = [r["model"] for r in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        self._set_cache("model_list", results)
        return results
    
    def get_monthly_sales(self, year=None):
        cache_key = f"monthly_sales_{year}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        if year:
            cursor.execute("""
                SELECT year, month, SUM(sales_amount) as monthly_sales, COUNT(*) as invoices
                FROM erp_pastinvoices 
                WHERE sales_amount > 0 AND year = %s
                GROUP BY year, month 
                ORDER BY year, month
            """, (year,))
        else:
            cursor.execute("""
                SELECT year, month, SUM(sales_amount) as monthly_sales, COUNT(*) as invoices
                FROM erp_pastinvoices 
                WHERE sales_amount > 0
                GROUP BY year, month 
                ORDER BY year DESC, month DESC
                LIMIT 36
            """)
        
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache(cache_key, results)
        return results
    
    def get_yearly_sales(self):
        if self._is_cache_valid("yearly_sales"):
            return self._cache["yearly_sales"]
        
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT year, COUNT(*) as invoice_count, SUM(sales_amount) as total_sales, SUM(item_qty) as total_qty
            FROM erp_pastinvoices 
            WHERE sales_amount > 0
            GROUP BY year 
            ORDER BY year
        """)
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        self._set_cache("yearly_sales", results)
        return results
    
    def search_invoices(self, query, limit=20):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT party, region, sales_person, brand, description, model, 
                   invoice_number, invoice_date, item_qty, sales_amount, grand_total_after_discount
            FROM erp_pastinvoices 
            WHERE party LIKE %s OR description LIKE %s OR brand LIKE %s OR model LIKE %s
            ORDER BY invoice_date DESC
            LIMIT %s
        """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return results
    
    def get_customers_by_region(self, region_query, limit=20):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Map common region names
        region_map = {
            "western": ["West-Mbarara", "West-Masaka", "West Nile"],
            "eastern": ["Eastern"],
            "northern": ["Northern", "Northwest", "North-West"],
            "central": ["Central"],
            "masaka": ["West-Masaka"],
            "mbarara": ["West-Mbarara"],
            "hoima": ["Hoima"],
            "luweero": ["Luwero"]
        }
        
        search_patterns = [f"%{region_query}%"]
        if region_query.lower() in region_map:
            for alias in region_map[region_query.lower()]:
                search_patterns.append(f"%{alias}%")
        
        placeholders = " OR ".join(["region LIKE %s"] * len(search_patterns))
        
        cursor.execute(f"""
            SELECT party as customer, region, sales_person,
                   COUNT(*) as invoice_count, SUM(sales_amount) as total_sales, MAX(invoice_date) as last_purchase
            FROM erp_pastinvoices 
            WHERE sales_amount > 0 AND ({placeholders})
            GROUP BY party, region, sales_person
            ORDER BY total_sales DESC
            LIMIT %s
        """, (*search_patterns, limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return results
    
    def get_brand_products(self, brand, limit=20):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT DISTINCT description as product, model, hsn, 
                   COUNT(*) as transactions, SUM(item_qty) as total_qty, AVG(sales_amount/item_qty) as avg_price
            FROM erp_pastinvoices 
            WHERE brand = %s AND description IS NOT NULL AND description != ''
            GROUP BY description, model, hsn
            ORDER BY total_qty DESC
            LIMIT %s
        """, (brand, limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return results
    
    def get_customer_history(self, customer_name, limit=10):
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT invoice_number, invoice_date, brand, description, model, 
                   item_qty, sales_amount, grand_total_after_discount
            FROM erp_pastinvoices 
            WHERE party LIKE %s
            ORDER BY invoice_date DESC
            LIMIT %s
        """, (f"%{customer_name}%", limit))
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return results
    
    def get_full_overview(self):
        return {
            "stats": self.get_total_stats(),
            "brands": self.get_sales_by_brand(10),
            "regions": self.get_sales_by_region(10),
            "salespersons": self.get_sales_by_salesperson(10),
            "top_customers": self.get_top_customers(10),
            "top_products": self.get_top_products(10),
            "yearly_sales": self.get_yearly_sales()
        }


class ERPNextDB:
    """Full database access for the chatbot."""
    
    def __init__(self):
        self.api_url = os.getenv("ERPNEXT_BASE_URL", "https://accounting.autozonepro.org").rstrip("/")
        self.api_key = os.getenv("ERP_API_KEY", "129e21e342fc921")
        self.api_secret = os.getenv("ERP_API_SECRET", "602231656cc1946")
        self.session = requests.Session()
        self.session.verify = False
        
    def _api_get(self, endpoint, params=None):
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"token {self.api_key}:{self.api_secret}"}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            return []

    # ============ ITEMS ============
    def get_items(self, search=None, brand=None, item_group=None, limit=50):
        filters = [["disabled", "=", 0]]
        if brand:
            filters.append(["brand", "=", brand])
        if search:
            filters.append(["item_name", "like", f"%{search}%"])
        if item_group:
            filters.append(["item_group", "=", item_group])
        return self._api_get("resource/Item", {
            "fields": json.dumps(["name", "item_code", "item_name", "brand", "item_group", "description", "stock_uom", "standard_rate"]),
            "filters": json.dumps(filters),
            "limit_page_length": limit
        })
    
    def get_all_items(self, limit=5000):
        return self._api_get("resource/Item", {
            "fields": json.dumps(["name", "item_code", "item_name", "brand", "item_group", "description"]),
            "filters": json.dumps([["disabled", "=", 0]]),
            "limit_page_length": limit
        })
    
    def get_item_count(self):
        return len(self.get_all_items(limit=5000))
    
    # ============ PRICES ============
    def get_prices(self, item_code=None, limit=100):
        filters = [["selling", "=", 1]]
        if item_code:
            filters.append(["item_code", "=", item_code])
        return self._api_get("resource/Item Price", {
            "fields": json.dumps(["name", "item_code", "price_list_rate", "currency", "price_list"]),
            "filters": json.dumps(filters),
            "limit_page_length": limit
        })
    
    def get_item_price(self, item_code):
        prices = self.get_prices(item_code=item_code, limit=1)
        return prices[0] if prices else None

    # ============ BRANDS ============
    def get_brands(self):
        items = self.get_all_items(limit=5000)
        brands = sorted(set(r.get("brand", "") for r in items if r.get("brand")))
        return brands
    
    def get_item_groups(self):
        items = self.get_all_items(limit=5000)
        groups = {}
        for r in items:
            g = r.get("item_group", "")
            if g:
                groups[g] = groups.get(g, 0) + 1
        return [{"item_group": k, "count": v} for k, v in sorted(groups.items(), key=lambda x: -x[1])]

    # ============ CUSTOMERS ============
    def get_customers(self, search=None, territory=None, limit=50):
        filters = [["docstatus", "<", 2]]
        if search:
            filters.append(["customer_name", "like", f"%{search}%"])
        if territory:
            filters.append(["territory", "=", territory])
        return self._api_get("resource/Customer", {
            "fields": json.dumps(["name", "customer_name", "customer_type", "customer_group", "territory", "mobile_no", "email_id"]),
            "filters": json.dumps(filters),
            "limit_page_length": limit
        })
    
    def get_all_customers(self, limit=10000):
        return self._api_get("resource/Customer", {
            "fields": json.dumps(["name", "customer_name", "customer_type", "territory"]),
            "filters": json.dumps([["docstatus", "<", 2]]),
            "limit_page_length": limit
        })
    
    def get_customer_count(self):
        return len(self.get_all_customers(limit=10000))

    # ============ TERRITORIES ============
    def get_territories(self):
        customers = self.get_all_customers(limit=10000)
        territories = sorted(set(c.get("territory", "") for c in customers if c.get("territory")))
        return territories if territories else ["Uganda"]

    # ============ SALES ============
    def get_sales_invoices(self, limit=50):
        return self._api_get("resource/Sales Invoice", {
            "fields": json.dumps(["name", "customer_name", "base_grand_total", "currency", "status", "posting_date", "outstanding_amount"]),
            "filters": json.dumps([["docstatus", "=", 1]]),
            "limit_page_length": limit
        })
    
    def get_sales_summary(self):
        invoices = self.get_sales_invoices(limit=1000)
        total = sum(i.get("base_grand_total", 0) or 0 for i in invoices)
        return {"count": len(invoices), "total": total}

    # ============ PURCHASES ============
    def get_purchase_invoices(self, limit=50):
        return self._api_get("resource/Purchase Invoice", {
            "fields": json.dumps(["name", "supplier_name", "base_grand_total", "status", "posting_date"]),
            "filters": json.dumps([["docstatus", "=", 1]]),
            "limit_page_length": limit
        })

    # ============ SUPPLIERS ============
    def get_suppliers(self, search=None, limit=50):
        filters = []
        if search:
            filters.append(["supplier_name", "like", f"%{search}%"])
        return self._api_get("resource/Supplier", {
            "fields": json.dumps(["name", "supplier_name", "supplier_group", "mobile_no"]),
            "filters": json.dumps(filters) if filters else None,
            "limit_page_length": limit
        })

    # ============ STOCK ============
    def get_stock_ledger(self, item_code=None, limit=50):
        filters = []
        if item_code:
            filters.append(["item_code", "=", item_code])
        return self._api_get("resource/Stock Ledger Entry", {
            "fields": json.dumps(["name", "item_code", "warehouse", "actual_qty", "posting_date"]),
            "filters": json.dumps(filters) if filters else None,
            "limit_page_length": limit
        })
    
    def get_warehouses(self):
        return self._api_get("resource/Warehouse", {
            "fields": json.dumps(["name", "warehouse_name"]),
            "limit_page_length": 100
        })

    # ============ QUOTATIONS ============
    def get_quotations(self, limit=50):
        return self._api_get("resource/Quotation", {
            "fields": json.dumps(["name", "customer_name", "base_grand_total", "status", "valid_until"]),
            "filters": json.dumps([["docstatus", "=", 1]]),
            "limit_page_length": limit
        })

    # ============ DELIVERY ============
    def get_delivery_notes(self, limit=50):
        return self._api_get("resource/Delivery Note", {
            "fields": json.dumps(["name", "customer_name", "base_grand_total", "status", "posting_date"]),
            "filters": json.dumps([["docstatus", "=", 1]]),
            "limit_page_length": limit
        })

    # ============ SUMMARY STATS ============
    def get_full_stats(self):
        brands = self.get_brands()
        territories = self.get_territories()
        items = self.get_item_count()
        customers = self.get_customer_count()
        sales = self.get_sales_summary()
        
        return {
            "total_items": items,
            "total_customers": customers,
            "total_brands": len(brands),
            "total_territories": len(territories),
            "brands": brands,
            "territories": territories,
            "total_sales": sales["total"],
            "total_invoices": sales["count"]
        }


def analyze_question(question: str) -> Dict[str, Any]:
    """Analyze the question to determine intent and extract entities."""
    q = question.lower()
    
    # Detect intents
    intents = []
    entities = {"search_terms": [], "brand": None, "territory": None, "customer": None, "item_code": None, "year": None}
    
    # Greetings
    if any(w in q for w in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"]):
        intents.append("greeting")
    
    # About the business
    if any(w in q for w in ["about", "who are you", "what is autozone", "your company", "company info", "tell me about"]):
        intents.append("about")
    
    # Contact info
    if any(w in q for w in ["contact", "phone", "email", "call", "reach", "address", "location", "hours", "open", "working hours"]):
        intents.append("contact")
    
    # Services
    if any(w in q for w in ["service", "services", "offer", "what do you provide", "what can you do", "what do you sell"]):
        intents.append("services")
    
    # Historical Sales Analysis
    if any(w in q for w in ["history", "historical", "past", "previous", "performance", "trends", "analysis", "sales history"]):
        intents.append("historical")
    
    # Top performers / Best sellers
    if any(w in q for w in ["top", "best", "leading", "highest", "most sold", "top selling", "popular", "fastest selling"]):
        intents.append("top_performers")
    
    # Year comparison
    if any(str(y) in q for y in range(2020, 2027)):
        import re
        years = re.findall(r'\b(202[0-6])\b', q)
        if years:
            entities["year"] = int(years[0])
            intents.append("yearly_stats")
    
    # Monthly stats
    if any(w in q for w in ["monthly", "this month", "last month", "per month", "this year"]):
        intents.append("monthly_stats")
    
    # Brands - check BEFORE items (since "have" triggers items)
    if any(w in q for w in ["brand", "brands", "carries", "sell", "what brands", "which brands", "list brands", "manufacturers", "make", "who supplies"]):
        intents.append("brands")
    
    # Items/Products - only if no specific brand intent
    if "items" not in intents and any(w in q for w in ["item", "product", "part", "spare", "available", "stock", "have", "in stock", "do you have", "do you sell", "looking for", "need", "want"]) or "show" in q:
        intents.append("items")
        entities["search_terms"].append(extract_search_term(question))
    
    # Prices/Costs - check BEFORE items to prioritize
    if any(w in q for w in ["price", "prices", "cost", "how much", "shilling", "ugx", "quote", "rate", "charges", "fee"]):
        intents.append("prices")
        entities["search_terms"].append(extract_search_term(question))
    
    # Customers / Garages
    if any(w in q for w in ["customer", "customers", "client", "clients", "garage", "garages", "shop", "shops", "workshop", "workshops", "buyer", "buyers"]):
        intents.append("customers")
        entities["search_terms"].append(extract_search_term(question))
    
    # Territories/Regions
    if any(w in q for w in ["region", "regions", "territory", "territories", "area", "areas", "location", "where", "uganda", "kampala", "coverage", "deliver"]):
        intents.append("territories")
    
    # Sales Persons - check BEFORE general sales
    if any(w in q for w in ["sales person", "sales persons", "salesperson", "salesmen", "sales man", "team member", "rep", "representative", "sales team", "contact person"]):
        intents.append("salespersons")
        intents.append("territories")  # Also include territories for regional info
    
    # Sales/Transactions
    if any(w in q for w in ["sale", "sales", "invoice", "invoices", "transaction", "transactions", "sold", "revenue", "turnover"]):
        intents.append("sales")
    
    # Suppliers
    if any(w in q for w in ["supplier", "suppliers", "vendor", "vendors", "supply", "source", "import"]):
        intents.append("suppliers")
        entities["search_terms"].append(extract_search_term(question))
    
    # Quotations
    if any(w in q for w in ["quotation", "quote", "quotes", "rfq", "request for quote", "estimate", "quotation"]):
        intents.append("quotations")
    
    # Stock/Inventory
    if any(w in q for w in ["stock", "inventory", "warehouse", "qty", "quantity", "availability", "in stock", "out of stock"]):
        intents.append("stock")
        entities["search_terms"].append(extract_search_term(question))
    
    # Summary/Stats
    if any(w in q for w in ["how many", "total", "summary", "stats", "statistics", "overview", "report", "numbers"]):
        intents.append("stats")
    
    # Catalog/Products list for a brand
    if any(w in q for w in ["catalog", "catalogue", "products list", "items list", "parts list", "all products", "all items", "full list"]):
        intents.append("catalog")
    
    # Most selling/Most popular/Ranking
    if any(w in q for w in ["most selling", "most popular", "best selling", "top selling", "ranking", "best brands", "selling brands"]):
        intents.append("top_performers")
        if "brand" not in intents:
            intents.append("brands")
    
    # CEO/Management/Company info
    if any(w in q for w in ["ceo", "cfo", "cto", "director", "manager", "management", "owner", "founder", "leadership", "management team"]):
        intents.append("management")
    
    # Supported motorcycle models list - check FIRST using phrase matching
    models_list_phrases = ["supported models", "which bikes", "what bikes", "what motorcycles", "list models", 
                          "motorcycle models", "bike models", "show me bike models", "show bike models",
                          "what models", "all models", "available models"]
    if any(phrase in q for phrase in models_list_phrases):
        intents.append("models_list")
    # Models / Bike compatibility - check AFTER models_list
    elif any(w in q for w in ["model", "bike", "motorcycle", "compatible", "fits", "applies to", "for bike", "for model", "bikes", "motorcycles"]):
        intents.append("models")
        entities["search_terms"].append(extract_search_term(question))
    
    # Default to general search
    if not intents:
        intents.append("general")
        entities["search_terms"].append(question)
    
    # Extract brand
    brands_keywords = ["hero", "bajaj", "tvs", "endurance", "adnoc", "lumax", "gabriel", "nada", "gold star", 
                      "tv s", "varroc", "rgl", "reve", "itq", "calender", "darshnam", "nbc", "key chains", "double glass", 
                      "gds", "ramp", "goldenboy", "special tools", "ace helmet", "armour helmet", "swara helmet",
                      "helmet", "aerostar visor", "visor"]
    for brand in brands_keywords:
        if brand in q:
            entities["brand"] = brand.title() if brand.lower() not in ["tv s", "gds", "rgl", "nada", "nbc", "itq"] else brand.upper()
            if brand.lower() == "tv s":
                entities["brand"] = "TVS"
            elif brand.lower() == "gds":
                entities["brand"] = "GDS"
            elif brand.lower() == "rgl":
                entities["brand"] = "RGL"
            elif brand.lower() == "nada":
                entities["brand"] = "NADA"
            elif brand.lower() == "nbc":
                entities["brand"] = "NBC"
            elif brand.lower() == "itq":
                entities["brand"] = "ITQ"
            break
            break
    
    # Extract item code
    import re
    codes = re.findall(r'\b[A-Z0-9]{4,}\b', question.upper())
    if codes:
        entities["item_code"] = codes[0]
    
    return {"intents": intents, "entities": entities, "original": question}


def answer_question(question: str) -> Dict[str, Any]:
    """Main function to answer any question about the database."""
    
    # Initialize learning system
    learning = ChatbotLearningSystem()
    
    # Check if we have a learned answer for this (or similar) question
    learned = learning.find_learned_answer(question, threshold=0.85)
    if learned and learned.get('match_score', 0) >= 0.85:
        # Found a very similar learned question - use it
        result = {
            "answer": learned['answer'],
            "intents": [learned.get('intent', 'learned')],
            "learned": True,
            "match_score": learned.get('match_score', 0)
        }
        # Still learn from this interaction
        learning.learn(question, learned['answer'], learned.get('intent'), success=True)
        return result
    
    db = ERPNextDB()
    hist = HistoricalData()
    analysis = analyze_question(question)
    intents = analysis["intents"]
    entities = analysis["entities"]
    primary_intent = intents[0] if intents else "general"
    
    # Get full stats once
    stats = db.get_full_stats()
    
    # Build response based on primary intent
    response_parts = []
    
    # Handle historical data intents
    if primary_intent in ["historical", "top_performers", "yearly_stats", "monthly_stats", "models_list", "models"]:
        result = answer_historical_question(question, intents, entities, stats, hist)
        # Learn from this interaction
        learning.learn(question, result['answer'], primary_intent, success=True)
        return result
    
    if primary_intent == "greeting":
        result = {
            "answer": build_greeting_response(stats),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'greeting', success=True)
        return result
    
    if primary_intent == "about":
        result = {
            "answer": build_about_response(stats),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'about', success=True)
        return result
    
    if primary_intent == "contact":
        result = {
            "answer": build_contact_response(),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'contact', success=True)
        return result
    
    if primary_intent == "services":
        result = {
            "answer": build_services_response(),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'services', success=True)
        return result
    
    if primary_intent == "stats":
        result = {
            "answer": build_stats_response(stats),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'stats', success=True)
        return result
    
    if primary_intent == "brands":
        brand = entities.get("brand")
        if brand:
            products = hist.get_brand_products(brand, limit=20)
            result = {
                "answer": build_brand_products_response(brand, products),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'brands', success=True)
            return result
        if "top_performers" in intents or "selling" in question.lower():
            brands_data = hist.get_sales_by_brand(limit=23)
            result = {
                "answer": build_brands_response(stats, brands_data),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'brands', success=True)
            return result
        result = {
            "answer": build_brands_response(stats),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'brands', success=True)
        return result
    
    if primary_intent == "items":
        full_search = entities["search_terms"][0] if entities["search_terms"] else None
        brand = entities.get("brand")
        
        # Use first word for ERPNext search (API doesn't support multi-word)
        search = full_search.split()[0] if full_search else None
        
        # Search BOTH ERPNext AND Historical data
        erp_items = db.get_items(search=search, brand=brand, limit=20)
        hist_items = hist.search_invoices(full_search, limit=50) if full_search else []
        
        item_code = entities.get("item_code")
        if item_code:
            all_items = db.get_items(limit=100)
            erp_items = [i for i in all_items if item_code.lower() in str(i.get("item_code", "")).lower() or item_code.lower() in str(i.get("item_name", "")).lower()]
        
        # Combine results from both sources
        combined_items = []
        seen_codes = set()
        
        # Add ERPNext items first
        for item in erp_items:
            code = item.get("item_code", "")
            if code and code not in seen_codes:
                combined_items.append({"source": "erpnext", **item})
                seen_codes.add(code)
        
        # Add historical items
        for h in hist_items[:30]:
            desc = h.get("description", "")
            if desc and desc not in seen_codes:
                combined_items.append({
                    "source": "historical",
                    "item_name": desc,
                    "brand": h.get("brand", ""),
                    "model": h.get("model", ""),
                    "hsn": h.get("hsn", ""),
                    "qty_sold": h.get("item_qty", 0),
                    "avg_price": h.get("avg_price", 0)
                })
                seen_codes.add(desc)
        
        if combined_items:
            result = {
                "answer": build_combined_items_response(combined_items, search, brand),
                "intents": intents,
                "stats": stats,
                "items_found": len(combined_items)
            }
            learning.learn(question, result['answer'], 'items', success=True)
            return result
        
        # Try partial word search
        if search:
            words = search.split()
            for word in words:
                if len(word) > 2:
                    partial_items = hist.search_invoices(word, limit=30)
                    if partial_items:
                        result = {
                            "answer": build_historical_items_response(word, partial_items),
                            "intents": intents,
                            "stats": stats,
                            "items_found": len(partial_items)
                        }
                        learning.learn(question, result['answer'], 'items', success=True)
                        return result
        
        # Nothing found
        result = {
            "answer": build_items_response([], search, brand),
            "intents": intents,
            "stats": stats,
            "items_found": 0
        }
        learning.record_unanswered(question)
        return result
    
    if primary_intent == "customers":
        search = entities["search_terms"][0] if entities["search_terms"] else None
        region = entities.get("territory")
        
        q_lower = question.lower()
        region_keywords = ["western", "eastern", "northern", "southern", "central", "masaka", "mbarara", "hoima", "luweero", "kampala", "entebbe"]
        
        found_region = None
        for keyword in region_keywords:
            if keyword in q_lower:
                found_region = keyword.title()
                break
        
        if found_region:
            region_customers = hist.get_customers_by_region(found_region, limit=20)
            result = {
                "answer": build_region_customers_response(found_region, region_customers),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'customers', success=True)
            return result
        
        if search:
            history = hist.get_customer_history(search, limit=10)
            if history:
                result = {
                    "answer": build_customer_history_response(search, history),
                    "intents": intents,
                    "stats": stats
                }
                learning.learn(question, result['answer'], 'customers', success=True)
                return result
        
        customers = db.get_customers(search=search, territory=region, limit=30)
        result = {
            "answer": build_customers_response(customers, search),
            "intents": intents,
            "stats": stats
        }
        if not customers:
            learning.record_unanswered(question)
        else:
            learning.learn(question, result['answer'], 'customers', success=True)
        return result
    
    if primary_intent == "salespersons":
        salespersons = hist.get_sales_by_salesperson(limit=20)
        result = {
            "answer": build_salespersons_response(salespersons),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'salespersons', success=True)
        return result
    
    if primary_intent == "territories":
        regions = hist.get_sales_by_region(limit=15)
        result = {
            "answer": build_territories_historical_response(regions),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'territories', success=True)
        return result
    
    if primary_intent == "sales":
        yearly = hist.get_yearly_sales()
        result = {
            "answer": build_yearly_sales_response(yearly),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'sales', success=True)
        return result
    
    if primary_intent == "catalog":
        brand = entities.get("brand")
        if brand:
            products = hist.get_brand_products(brand, limit=50)
            result = {
                "answer": build_brand_catalog_response(brand, products),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'catalog', success=True)
            return result
        brands = hist.get_sales_by_brand(limit=23)
        result = {
            "answer": build_all_brands_catalog_response(brands),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'catalog', success=True)
        return result
    
    if primary_intent == "management":
        result = {
            "answer": build_management_response(),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'management', success=True)
        return result
    
    if primary_intent == "suppliers":
        search = entities["search_terms"][0] if entities["search_terms"] else None
        suppliers = db.get_suppliers(search=search, limit=20)
        result = {
            "answer": build_suppliers_response(suppliers),
            "intents": intents,
            "stats": stats
        }
        if not suppliers:
            learning.record_unanswered(question)
        else:
            learning.learn(question, result['answer'], 'suppliers', success=True)
        return result
    
    if primary_intent == "prices":
        full_search = entities["search_terms"][0] if entities["search_terms"] else None
        brand = entities.get("brand")
        
        # Use first word for ERPNext search (API doesn't support multi-word)
        search = full_search.split()[0] if full_search else None
        
        # Search BOTH ERPNext AND Historical for prices
        items = db.get_items(search=search, brand=brand, limit=20)
        prices_data = []
        for item in items[:10]:
            price = db.get_item_price(item.get("item_code"))
            if price:
                prices_data.append({"item": item, "price": price, "source": "erpnext"})
        
        # Also get historical prices (use full search term)
        if full_search:
            hist_prices = hist.search_invoices(full_search, limit=30)
            if hist_prices:
                prices_data.extend([{"item": h, "price": h, "source": "historical"} for h in hist_prices])
        
        if prices_data:
            result = {
                "answer": build_combined_prices_response(prices_data, search, brand),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'prices', success=True)
            return result
        
        result = {
            "answer": "I couldn't find pricing information for your search. Please try a different product name or brand.",
            "intents": intents,
            "stats": stats
        }
        learning.record_unanswered(question)
        return result
    
    if primary_intent == "quotations":
        quotations = db.get_quotations(limit=20)
        result = {
            "answer": build_quotations_response(quotations),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'quotations', success=True)
        return result
    
    if primary_intent == "stock":
        search = entities["search_terms"][0] if entities["search_terms"] else None
        warehouses = db.get_warehouses()
        result = {
            "answer": build_stock_response(warehouses, search),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'stock', success=True)
        return result
    
    # Default: general search
    result = {
        "answer": build_general_response(question, db, entities),
        "intents": intents,
        "stats": stats
    }
    learning.record_unanswered(question)
    return result


def answer_historical_question(question: str, intents: List, entities: Dict, stats: Dict, hist: HistoricalData) -> Dict[str, Any]:
    """Handle historical sales data questions."""
    
    learning = ChatbotLearningSystem()
    q = question.lower()
    
    if "models_list" in intents:
        models = hist.get_model_list()
        result = {
            "answer": build_models_list_response(models),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'models_list', success=True)
        return result
    
    if "models" in intents:
        search = entities["search_terms"][0] if entities["search_terms"] else None
        if search:
            parts = hist.search_by_model(search, limit=30)
            result = {
                "answer": build_model_parts_response(search, parts),
                "intents": intents,
                "stats": stats
            }
            learning.learn(question, result['answer'], 'models', success=True)
            return result
    
    if "top_performers" in intents:
        top_customers = hist.get_top_customers(10)
        top_products = hist.get_top_products(10)
        top_brands = hist.get_sales_by_brand(10)
        top_salespersons = hist.get_sales_by_salesperson(10)
        
        result = {
            "answer": build_top_performers_response(top_customers, top_products, top_brands, top_salespersons),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'top_performers', success=True)
        return result
    
    if "yearly_stats" in intents and entities.get("year"):
        year = entities["year"]
        monthly = hist.get_monthly_sales(year)
        result = {
            "answer": build_year_stats_response(year, monthly),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'yearly_stats', success=True)
        return result
    
    if "monthly_stats" in intents:
        monthly = hist.get_monthly_sales()[:12]
        result = {
            "answer": build_monthly_stats_response(monthly),
            "intents": intents,
            "stats": stats
        }
        learning.learn(question, result['answer'], 'monthly_stats', success=True)
        return result
    
    overview = hist.get_full_overview()
    result = {
        "answer": build_historical_overview_response(overview),
        "intents": intents,
        "stats": stats
    }
    learning.learn(question, result['answer'], 'historical', success=True)
    return result


def build_greeting_response(stats):
    total_sales = stats.get('total_sales', 0) or 0
    total_items = stats.get('total_items', 0) or 0
    total_customers = stats.get('total_customers', 0) or 0
    total_brands = stats.get('total_brands', 0) or 0
    total_invoices = stats.get('total_invoices', 0) or 0
    
    return f"""Hello! Welcome to AutoZone Pro! I'm your AI assistant with full access to our complete database.

Here's our business overview based on actual data:

BUSINESS OVERVIEW:
- Total Invoices Processed: {total_invoices:,}
- Total Revenue: {format_ugx(total_sales)}
- Active Products: {total_items:,}
- Partner Brands: {total_brands}
- Registered Customers: {total_customers:,}

TOP SELLING BRANDS:
• Endurance - Leading brand with highest sales
• Reve - Strong market presence
• Bajaj - OEM parts specialist
• Varroc - Quality automotive parts
• Gabriel - Premium shock absorbers
• Lumax - Lighting and electrical

I can help you with:
• Products - Search by name, brand, or item code
• Prices - Get current pricing and historical rates
• Customers - View customer information
• Sales - Transaction history and trends
• Regions - Coverage across Uganda
• Sales Team - Contact our representatives
• And much more!

What would you like to know about?"""


def build_about_response(stats):
    total_sales = stats.get('total_sales', 0) or 0
    total_brands = stats.get('total_brands', 0) or 0
    
    return f"""AUTOZONE PRO PROFESSIONAL LIMITED

Uganda's trusted auto spare parts distributor with proven track record.

BUSINESS OVERVIEW:
• Total Revenue (2020-2026): {format_ugx(total_sales)}
• Active Brands: {total_brands}
• Products: Motorcycle and automotive spare parts

OUR SPECIALIZATION:
• Motorcycle parts: Hero, Bajaj, TVS, Endurance, Reve, and more
• Automotive parts: Gabriel shocks, Lumax lighting, Varroc electrical
• OEM quality parts for all major brands

TOP SELLING CATEGORIES:
• Shock absorbers (Endurance, Gabriel)
• Clutch plates and kits (Endurance, Reve)
• Bearings (NBC, Bajaj)
• Electrical parts (Lumax, Varroc)
• Body parts (Reve)

SERVICE REGIONS:
• Central Uganda (Kampala area)
• Western Uganda (Mbarara, Masaka, Hoima)
• Eastern Uganda (Jinja, Tororo)
• Northern Uganda (Lira, Gulu)
• West Nile region

CONTACT US:
• Location: Kawempe Mbogo Road, opposite Mbogo College
• Email: crm@autozonepro.org
• Website: autozonepro.org
• Hours: Monday - Saturday, 8:00 AM - 6:00 PM

Ask me about specific products, prices, or your account!"""


def build_contact_response():
    return """CONTACT AUTOZONE PRO

📍 PHYSICAL ADDRESS:
Kawempe Mbogo Road, opposite Mbogo College
Uganda

📧 EMAIL:
crm@autozonepro.org

📱 PHONE:
+256 700 123 456

⏰ BUSINESS HOURS:
Monday - Friday: 8:00 AM - 6:00 PM
Saturday: 8:00 AM - 6:00 PM
Sunday: Closed

🌐 WEBSITE:
www.autozonepro.org

For inquiries, quotes, or support, please don't hesitate to contact us!"""


def build_services_response():
    return """AUTOZONE PRO SERVICES

We offer comprehensive auto spare parts solutions:

1. PRODUCT RANGE
   • Motorcycle spare parts (Hero, Bajaj, TVS, Endurance)
   • Automotive components
   • Garage equipment
   • Tools and accessories

2. SALES OPTIONS
   • Wholesale supply
   • Retail sales
   • Bulk orders

3. DELIVERY
   • Fast delivery across Uganda
   • Multiple pickup points
   • Reliable shipping

4. SUPPORT
   • Technical advice
   • Product recommendations
   • Order tracking

5. BUSINESS CUSTOMERS
   • Garage partnerships
   • Fleet supply contracts
   • Credit facilities for established businesses

Would you like more details on any specific service?"""


def build_stats_response(stats):
    return f"""BUSINESS STATISTICS

PRODUCTS:
• Total Items: {stats['total_items']:,}
• Total Brands: {stats['total_brands']}

CUSTOMERS:
• Total Customers: {stats['total_customers']:,}

SALES:
• Total Invoices: {stats['total_invoices']:,}
• Total Revenue: {stats['total_sales']:,.0f} UGX

REGIONS:
• Service Regions: {stats['total_territories']}
• All major areas in Uganda covered

Would you like more detailed information on any of these?"""


def build_brands_response(stats, brands_data=None):
    """Build response for brands. If brands_data provided, show ranked by sales."""
    if brands_data:
        result = "TOP SELLING BRANDS - RANKED BY REVENUE\n"
        result += "(Based on 2020-2026 sales data)\n\n"
        result += "=" * 50 + "\n"
        result += "RANK | BRAND              | SALES\n"
        result += "=" * 50 + "\n"
        for i, b in enumerate(brands_data[:15], 1):
            name = b.get("brand", "N/A")[:18]
            sales = float(b.get("total_sales", 0) or 0)
            result += f"{i:4d} | {name:18s} | {format_ugx(sales)}\n"
        result += "=" * 50 + "\n\n"
        result += "To see products for a brand, ask: 'Show me Endurance products'"
        return result
    
    brands_list = ", ".join(stats['brands'])
    return f"""OUR BRANDS ({stats['total_brands']} total)

We carry parts from these manufacturers:

{brands_list}

Our main focus is on motorcycle brands like Hero, Bajaj, TVS, and Endurance, but we also carry automotive parts from various other brands.

Would you like to see products from a specific brand?"""


def build_items_response(items, search, brand):
    if not items:
        msg = "I couldn't find any items matching your search."
        if search:
            msg += f"\n\nSearch term: {search}"
        if brand:
            msg += f"\nBrand: {brand}"
        msg += "\n\nTry searching for a different item name or brand."
        return msg
    
    result = f"Found {len(items)} items:\n\n"
    for item in items[:15]:
        name = item.get("item_name", "N/A")
        code = item.get("item_code", "N/A")
        item_brand = item.get("brand", "N/A")
        group = item.get("item_group", "N/A")
        result += f"• {name}\n  Code: {code} | Brand: {item_brand} | Type: {group}\n\n"
    
    if len(items) > 15:
        result += f"\n...and {len(items) - 15} more items.\n"
    
    result += "\nWould you like to see prices or more details?"
    return result


def build_prices_response(prices_data, search, brand):
    if not prices_data:
        return "I couldn't find pricing information for your search. Please try a different product name or brand."
    
    result = "PRICING INFORMATION:\n\n"
    for entry in prices_data[:15]:
        item = entry["item"]
        price = entry["price"]
        name = item.get("item_name", "N/A")
        code = item.get("item_code", "N/A")
        rate = price.get("price_list_rate", 0)
        currency = price.get("currency", "UGX")
        result += f"• {name} ({code})\n  Price: {rate:,.0f} {currency}\n\n"
    
    result += "Note: Prices may vary. Contact us for exact quotes and availability."
    return result


def build_customers_response(customers, search):
    if not customers:
        msg = "I couldn't find any customers matching your search."
        if search:
            msg += f"\nSearch term: {search}"
        return msg
    
    result = f"Found {len(customers)} customers:\n\n"
    for cust in customers[:20]:
        name = cust.get("customer_name", "N/A")
        cust_type = cust.get("customer_type", "N/A")
        territory = cust.get("territory", "Uganda")
        mobile = cust.get("mobile_no", "")
        result += f"• {name}\n  Type: {cust_type} | Region: {territory}"
        if mobile:
            result += f" | Mobile: {mobile}"
        result += "\n\n"
    
    if len(customers) > 20:
        result += f"\n...and {len(customers) - 20} more customers."
    
    return result


def build_territories_response(stats):
    territories_list = "\n".join(f"• {t}" for t in stats['territories'])
    return f"""SERVICE REGIONS ({stats['total_territories']} total)

We serve customers across these regions in Uganda:

{territories_list}

Our coverage includes major towns and rural areas throughout the country.

Contact us to check if we serve your specific location!"""


def build_sales_response(sales, summary):
    result = f"SALES OVERVIEW\n\n"
    result += f"Total Invoices: {summary['count']}\n"
    result += f"Total Revenue: {summary['total']:,.0f} UGX\n\n"
    result += "RECENT TRANSACTIONS:\n\n"
    
    for inv in sales[:10]:
        name = inv.get("name", "N/A")
        customer = inv.get("customer_name", "N/A")
        amount = inv.get("base_grand_total", 0) or 0
        status = inv.get("status", "N/A")
        result += f"• Invoice {name}\n  Customer: {customer}\n  Amount: {amount:,.0f} UGX | Status: {status}\n\n"
    
    return result


def build_suppliers_response(suppliers):
    if not suppliers:
        return "I couldn't find any suppliers matching your search."
    
    result = f"Found {len(suppliers)} suppliers:\n\n"
    for sup in suppliers[:20]:
        name = sup.get("supplier_name", "N/A")
        group = sup.get("supplier_group", "N/A")
        mobile = sup.get("mobile_no", "")
        result += f"• {name}\n  Type: {group}"
        if mobile:
            result += f" | Mobile: {mobile}"
        result += "\n\n"
    
    return result


def build_quotations_response(quotations):
    if not quotations:
        return "No recent quotations found."
    
    result = f"RECENT QUOTATIONS:\n\n"
    for q in quotations[:10]:
        name = q.get("name", "N/A")
        customer = q.get("customer_name", "N/A")
        amount = q.get("base_grand_total", 0) or 0
        valid = q.get("valid_until", "N/A")
        result += f"• {name}\n  Customer: {customer}\n  Amount: {amount:,.0f} UGX\n  Valid Until: {valid}\n\n"
    
    return result


def build_stock_response(warehouses, search):
    result = "WAREHOUSES/INVENTORY LOCATIONS:\n\n"
    for wh in warehouses[:10]:
        name = wh.get("warehouse_name", "N/A")
        result += f"• {name}\n"
    
    if search:
        result += f"\n\nFor detailed stock levels of '{search}', please contact us directly."
    else:
        result += "\n\nFor detailed stock inquiries, please ask about specific items."
    
    return result


def build_general_response(question, db, entities):
    # Do a broad search
    search = entities.get("search_terms", [None])[0] or extract_search_term(question)
    
    stats = db.get_full_stats()
    
    # Try searching items
    items = db.get_items(search=search, limit=10) if search else []
    
    if items:
        return f"I found these items related to your query '{search}'\n\n" + build_items_response(items, search, None)
    
    # Try searching customers
    customers = db.get_customers(search=search, limit=10) if search else []
    
    if customers:
        return f"I found these customers related to '{search}'\n\n" + build_customers_response(customers, search)
    
    # No results - give a helpful response
    return f"""I couldn't find specific information matching your query: "{question}"

Here's what I can help you with:

• Search for products by name, brand, or item code
• Get pricing information
• View customer lists
• Check sales transactions
• Find supplier information
• View business statistics
• Learn about our services

Try asking something like:
• "Do you have Hero brake pads?"
• "What's the price of [item name]?"
• "Show me customers in [region]"
• "What brands do you carry?"
• "How many invoices this month?"

How can I help you?"""


def extract_search_term(question: str) -> Optional[str]:
    """Extract meaningful search terms from question - removes intent words too."""
    # Remove articles, prepositions, and intent-related words
    stop_words = {
        # Articles/prepositions
        "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "i", "it",
        # Intent-related words
        "price", "prices", "cost", "how", "much", "show", "me", "find", "get", "look",
        "search", "list", "available", "tell", "what", "which", "who", "where",
        "when", "is", "are", "was", "were", "have", "has", "had", "do", "does", "did",
        "can", "could", "would", "should", "will", "shall", "may", "might"
    }
    
    words = question.lower().replace("?", "").replace(",", "").replace(".", "").replace("-", " ").replace("/", " ").split()
    
    # Filter out stop words and very short words
    filtered = [w for w in words if w not in stop_words and len(w) > 1]
    
    term = " ".join(filtered)
    return term if term else None


def format_ugx(amount: float) -> str:
    """Format amount in Ugandan Shillings."""
    if amount >= 1_000_000_000:
        return f"UGX {amount/1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"UGX {amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"UGX {amount/1_000:.2f}K"
    return f"UGX {amount:,.0f}"


def build_brand_products_response(brand: str, products: List) -> str:
    """Build response for brand-specific products."""
    if not products:
        return f"I don't have historical sales data for {brand} products."
    
    result = f"HISTORICAL SALES DATA FOR {brand.upper()} PRODUCTS\n"
    result += f"(Based on 2020-2026 transaction records)\n\n"
    result += f"Top {brand} Products by Quantity Sold:\n\n"
    
    for i, p in enumerate(products[:15], 1):
        qty = float(p.get("total_qty", 0) or 0)
        sales = float(p.get("total_sales", 0) or 0)
        avg_price = float(p.get("avg_price", 0) or 0)
        result += f"{i}. {p.get('product', 'N/A')}\n"
        result += f"   Qty Sold: {qty:,.0f} units | Total Sales: {format_ugx(sales)}"
        if avg_price > 0:
            result += f" | Avg Price: {format_ugx(avg_price)}"
        result += "\n"
        if p.get('model'):
            result += f"   Model: {p.get('model')}\n"
        result += "\n"
    
    return result


def build_customer_history_response(customer: str, history: List) -> str:
    """Build response for customer purchase history."""
    result = f"PURCHASE HISTORY FOR '{customer.upper()}'\n"
    result += "(Based on historical records)\n\n"
    
    total_sales = sum(float(h.get("sales_amount", 0) or 0) for h in history)
    
    result += f"Recent Purchases ({len(history)} records):\n\n"
    
    for h in history[:10]:
        date = h.get("invoice_date", "N/A")
        brand = h.get("brand", "")
        desc = h.get("description", "N/A")
        qty = float(h.get("item_qty", 0) or 0)
        amount = float(h.get("sales_amount", 0) or 0)
        result += f"• {date} - {brand} {desc}\n"
        result += f"  Qty: {qty:,.0f} | Amount: {format_ugx(amount)}\n\n"
    
    result += f"\nTotal for shown records: {format_ugx(total_sales)}"
    
    return result


def build_territories_historical_response(regions: List) -> str:
    """Build response for territory/region sales."""
    result = "SALES BY REGION (2020-2026 Historical Data)\n\n"
    result += f"Total Regions: {len(regions)}\n\n"
    result += "TOP PERFORMING REGIONS:\n\n"
    
    for i, r in enumerate(regions[:12], 1):
        count = r.get("invoice_count", 0)
        sales = float(r.get("total_sales", 0) or 0)
        result += f"{i}. {r.get('region', 'N/A')}\n"
        result += f"   Invoices: {count:,} | Total Sales: {format_ugx(sales)}\n\n"
    
    return result


def build_yearly_sales_response(yearly: List) -> str:
    """Build response for yearly sales summary."""
    result = "ANNUAL SALES SUMMARY (2020-2026)\n\n"
    
    for y in yearly:
        year = y.get("year", "N/A")
        count = y.get("invoice_count", 0)
        sales = float(y.get("total_sales", 0) or 0)
        qty = float(y.get("total_qty", 0) or 0)
        result += f"{year}:\n"
        result += f"   Invoices: {count:,} | Sales: {format_ugx(sales)} | Qty: {qty:,.0f} units\n\n"
    
    return result


def build_top_performers_response(top_customers: List, top_products: List, top_brands: List, top_salespersons: List) -> str:
    """Build response for top performers."""
    result = "TOP PERFORMERS - BUSINESS INTELLIGENCE REPORT\n"
    result += "(Based on 201,467 invoices from 2020-2026)\n\n"
    
    result += "=" * 50 + "\n"
    result += "TOP 10 CUSTOMERS BY REVENUE\n"
    result += "=" * 50 + "\n\n"
    for i, c in enumerate(top_customers[:10], 1):
        sales = float(c.get("total_sales", 0) or 0)
        result += f"{i}. {c.get('customer', 'N/A')}\n"
        result += f"   Region: {c.get('region', 'N/A')} | Invoices: {c.get('invoice_count', 0)} | Sales: {format_ugx(sales)}\n\n"
    
    result += "=" * 50 + "\n"
    result += "TOP 10 BEST SELLING PRODUCTS\n"
    result += "=" * 50 + "\n\n"
    for i, p in enumerate(top_products[:10], 1):
        qty = float(p.get("total_qty", 0) or 0)
        result += f"{i}. {p.get('product', 'N/A')} ({p.get('brand', '')}) \n"
        result += f"   Qty Sold: {qty:,.0f} units\n\n"
    
    result += "=" * 50 + "\n"
    result += "TOP 10 BRANDS BY SALES\n"
    result += "=" * 50 + "\n\n"
    for i, b in enumerate(top_brands[:10], 1):
        sales = float(b.get("total_sales", 0) or 0)
        result += f"{i}. {b.get('brand', 'N/A')}: {format_ugx(sales)}\n"
    
    result += "\n" + "=" * 50 + "\n"
    result += "TOP 10 SALES PERSONS BY REVENUE\n"
    result += "=" * 50 + "\n\n"
    for i, s in enumerate(top_salespersons[:10], 1):
        sales = float(s.get("total_sales", 0) or 0)
        result += f"{i}. {s.get('sales_person', 'N/A')}: {format_ugx(sales)}\n"
    
    return result


def build_year_stats_response(year: int, monthly: List) -> str:
    """Build response for specific year statistics."""
    result = f"SALES PERFORMANCE FOR {year}\n\n"
    
    total_sales = sum(float(m.get("monthly_sales", 0) or 0) for m in monthly)
    total_invoices = sum(m.get("invoices", 0) for m in monthly)
    
    result += f"Year Total: {format_ugx(total_sales)}\n"
    result += f"Total Invoices: {total_invoices:,}\n\n"
    result += "MONTHLY BREAKDOWN:\n\n"
    
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    for m in monthly:
        month_num = m.get("month", 0)
        sales = float(m.get("monthly_sales", 0) or 0)
        invoices = m.get("invoices", 0)
        name = month_names[month_num - 1] if 1 <= month_num <= 12 else f"Month {month_num}"
        result += f"{name}: {format_ugx(sales)} ({invoices} invoices)\n"
    
    return result


def build_monthly_stats_response(monthly: List) -> str:
    """Build response for recent monthly statistics."""
    result = "RECENT MONTHLY SALES (Last 12 Months)\n\n"
    
    for m in monthly[:12]:
        year = m.get("year", "")
        month_num = m.get("month", 0)
        sales = float(m.get("monthly_sales", 0) or 0)
        invoices = m.get("invoices", 0)
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        name = month_names[month_num - 1] if 1 <= month_num <= 12 else f"Month {month_num}"
        result += f"{name} {year}: {format_ugx(sales)} ({invoices} invoices)\n"
    
    return result


def build_historical_overview_response(overview: Dict) -> str:
    """Build comprehensive historical overview."""
    stats = overview.get("stats", {})
    brands = overview.get("brands", [])
    regions = overview.get("regions", [])
    yearly = overview.get("yearly_sales", [])
    
    total_invoices = stats.get("total_invoices", 0) or 0
    total_sales = float(stats.get("total_sales", 0) or 0)
    total_customers = stats.get("total_customers", 0) or 0
    earliest = stats.get("earliest_date", "N/A")
    latest = stats.get("latest_date", "N/A")
    
    result = "AUTOZONE PRO - HISTORICAL BUSINESS OVERVIEW\n"
    result += "(Data from 2020 to 2026)\n\n"
    
    result += "=" * 50 + "\n"
    result += "KEY STATISTICS\n"
    result += "=" * 50 + "\n\n"
    result += f"Total Invoices: {total_invoices:,}\n"
    result += f"Total Revenue: {format_ugx(total_sales)}\n"
    result += f"Unique Customers: {total_customers:,}\n"
    result += f"Date Range: {earliest} to {latest}\n"
    
    result += "\n" + "=" * 50 + "\n"
    result += "SALES BY BRAND (Top 10)\n"
    result += "=" * 50 + "\n\n"
    for i, b in enumerate(brands[:10], 1):
        sales = float(b.get("total_sales", 0) or 0)
        result += f"{i}. {b.get('brand', 'N/A')}: {format_ugx(sales)}\n"
    
    result += "\n" + "=" * 50 + "\n"
    result += "SALES BY REGION (Top 10)\n"
    result += "=" * 50 + "\n\n"
    for i, r in enumerate(regions[:10], 1):
        sales = float(r.get("total_sales", 0) or 0)
        result += f"{i}. {r.get('region', 'N/A')}: {format_ugx(sales)}\n"
    
    result += "\n" + "=" * 50 + "\n"
    result += "ANNUAL TREND\n"
    result += "=" * 50 + "\n\n"
    for y in yearly:
        year = y.get("year", "N/A")
        sales = float(y.get("total_sales", 0) or 0)
        result += f"{year}: {format_ugx(sales)}\n"
    
    return result


class AutoZoneChatbot:
    """Wrapper class for chatbot compatibility with views."""
    
    def __init__(self):
        self.db = ERPNextDB()
        self.hist = HistoricalData()
    
    def get_brands(self):
        return self.db.get_brands()
    
    def get_territories(self):
        return self.db.get_territories()
    
    def get_item_count(self):
        return self.db.get_item_count()
    
    def get_customer_count(self):
        return self.db.get_customer_count()
    
    def get_total_stats(self):
        return self.hist.get_total_stats()
    
    def get_full_stats(self):
        """Get combined stats from ERPNext and historical data."""
        erp_stats = self.db.get_full_stats()
        hist_stats = self.hist.get_total_stats()
        
        return {
            'total_items': erp_stats.get('total_items', 0),
            'total_customers': erp_stats.get('total_customers', 0),
            'total_brands': len(self.db.get_brands()),
            'total_territories': len(self.db.get_territories()),
            'total_sales': hist_stats.get('total_sales', 0),
            'total_invoices': hist_stats.get('total_invoices', 0),
            'unique_items': hist_stats.get('unique_items', 0),
        }
    
    def get_sales_by_brand(self):
        return self.hist.get_sales_by_brand(limit=10)
    
    def get_sales_by_region(self):
        return self.hist.get_sales_by_region(limit=10)
    
    def get_yearly_sales(self):
        return self.hist.get_yearly_sales()
    
    def get_top_customers(self):
        return self.hist.get_top_customers(limit=10)
    
    def get_top_products(self, limit=20):
        return self.hist.get_top_products(limit=limit)
    
    def answer(self, question):
        return answer_question(question)


def build_salespersons_response(salespersons: List) -> str:
    """Build response showing all salespersons with their performance."""
    result = "SALES PERSONNEL AND THEIR PERFORMANCE\n"
    result += "(Based on 2020-2026 transaction data)\n\n"
    result += f"Total Sales Team: {len(salespersons)} members\n\n"
    result += "=" * 60 + "\n"
    result += "RANK | SALESPERSON      | INVOICES | TOTAL SALES\n"
    result += "=" * 60 + "\n"
    
    for i, sp in enumerate(salespersons, 1):
        name = sp.get("sales_person", "N/A")
        invoices = sp.get("invoice_count", 0)
        sales = float(sp.get("total_sales", 0) or 0)
        result += f"{i:4d} | {name[:16]:16s} | {invoices:8,d} | {format_ugx(sales)}\n"
    
    result += "=" * 60 + "\n"
    result += "\nNote: 'Office' refers to counter sales at the main office."
    
    return result


def build_brand_catalog_response(brand: str, products: List) -> str:
    """Build complete catalog for a specific brand."""
    result = f"{brand.upper()} PRODUCTS CATALOG\n"
    result += "(Based on historical sales data 2020-2026)\n\n"
    result += f"Total unique {brand} products: {len(products)}\n\n"
    result += "=" * 60 + "\n"
    result += "TOP PRODUCTS BY POPULARITY:\n"
    result += "=" * 60 + "\n\n"
    
    for i, p in enumerate(products[:30], 1):
        product_name = p.get("product", "N/A")
        model = p.get("model", "")
        hsn = p.get("hsn", "")
        qty = float(p.get("total_qty", 0) or 0)
        sales = float(p.get("total_sales", 0) or 0)
        avg_price = float(p.get("avg_price", 0) or 0)
        
        result += f"{i:2d}. {product_name}\n"
        if model:
            result += f"    Model: {model}\n"
        if hsn:
            result += f"    HSN: {hsn}\n"
        result += f"    Units Sold: {qty:,.0f} | Total Sales: {format_ugx(sales)}"
        if avg_price > 0:
            result += f" | Avg Price: {format_ugx(avg_price)}"
        result += "\n\n"
    
    if len(products) > 30:
        result += f"\n...and {len(products) - 30} more products.\n"
    
    result += "\nFor current pricing and availability, please contact us."
    
    return result


def build_all_brands_catalog_response(brands: List) -> str:
    """Build response showing all brands with product counts."""
    result = "COMPLETE BRAND CATALOG\n"
    result += "(Based on 2020-2026 sales data)\n\n"
    result += "=" * 60 + "\n"
    result += "BRAND                    | PRODUCTS | TOTAL SALES\n"
    result += "=" * 60 + "\n"
    
    for b in brands:
        brand_name = b.get("brand", "N/A")[:24]
        count = b.get("invoice_count", 0)
        sales = float(b.get("total_sales", 0) or 0)
        result += f"{brand_name:24s} | {count:8,d} | {format_ugx(sales)}\n"
    
    result += "=" * 60 + "\n"
    result += "\nTo see products for a specific brand, ask:\n"
    result += '"Show me all Endurance products" or "Catalog for Bajaj"'
    
    return result


def build_management_response() -> str:
    """Build response for company management/leadership questions."""
    return """AUTOZONE PRO MANAGEMENT

As an AI chatbot, I don't have access to specific personal information about our leadership team.

For inquiries about company management:
• Email: crm@autozonepro.org
• Phone: +256 700 123 456

COMPANY INFORMATION:
• Company: AutoZone Pro Professional Limited
• Business: Auto spare parts distribution
• Location: Kawempe Mbogo Road, opposite Mbogo College, Uganda
• Founded: Serving Uganda since 2015+
• Specialization: Motorcycle and automotive spare parts

For specific management inquiries, please contact our customer service team."""


def build_historical_prices_response(search: str, results: List) -> str:
    """Build response showing prices from historical sales data."""
    # Aggregate by product
    products = {}
    for r in results:
        key = f"{r.get('description', '')} ({r.get('brand', '')})"
        if key not in products:
            products[key] = {"name": r.get("description", "N/A"), "brand": r.get("brand", ""), "count": 0, "total_qty": 0, "total_sales": 0, "prices": []}
        qty = float(r.get("item_qty", 0) or 0)
        sales = float(r.get("sales_amount", 0) or 0)
        if qty > 0:
            avg_price = sales / qty
            products[key]["prices"].append(avg_price)
            products[key]["total_qty"] += qty
            products[key]["total_sales"] += sales
            products[key]["count"] += 1
    
    result = f"PRICING INFORMATION FOR '{search.upper()}'\n"
    result += "(Based on historical sales data - 2020-2026)\n\n"
    result += f"Found pricing data for {len(products)} products:\n\n"
    result += "=" * 60 + "\n"
    result += "PRODUCT                    | AVG PRICE   | QTY SOLD\n"
    result += "=" * 60 + "\n"
    
    for key, p in list(products.items())[:15]:
        avg_price = sum(p["prices"]) / len(p["prices"]) if p["prices"] else 0
        result += f"{key[:26]:26s} | {format_ugx(avg_price):11s} | {p['total_qty']:,.0f}\n"
    
    result += "=" * 60 + "\n"
    result += "\nNote: These are historical average prices. Current prices may vary.\n"
    result += "For exact current pricing, please contact us."
    
    return result


def build_region_customers_response(region: str, customers: List) -> str:
    """Build response showing customers in a specific region."""
    if not customers:
        return f"I couldn't find any customers in the '{region}' region.\n\nPlease try a different region name or contact us for assistance."
    
    result = f"CUSTOMERS IN {region.upper()} REGION\n"
    result += "(Based on 2020-2026 transaction data)\n\n"
    result += f"Found {len(customers)} customers in this region:\n\n"
    result += "=" * 70 + "\n"
    result += "CUSTOMER                 | REGION              | SALES     | LAST PURCHASE\n"
    result += "=" * 70 + "\n"
    
    for c in customers[:20]:
        name = c.get("customer", "N/A")[:23]
        reg = c.get("region", "N/A")[:19]
        sales = float(c.get("total_sales", 0) or 0)
        last = c.get("last_purchase", "N/A")
        if hasattr(last, 'strftime'):
            last = last.strftime("%Y-%m-%d")
        result += f"{name:23s} | {reg:19s} | {format_ugx(sales):11s} | {last}\n"
    
    result += "=" * 70 + "\n"
    
    if len(customers) > 20:
        result += f"\n...and {len(customers) - 20} more customers in this region."
    
    return result


def build_model_parts_response(model: str, parts: List) -> str:
    """Build response showing parts compatible with a specific bike model."""
    if not parts:
        return f"I don't have parts data for '{model}' motorcycles.\n\nSupported models include:\n• BM100KS, BM100ES, BM150 (Bajaj)\n• CT125, Discover, Pulsar\n• Hero-Hunter, Destini, XPulse\n• TVS HLX, Apache, Victor\n\nPlease try searching for your bike model."
    
    result = f"PARTS FOR '{model.upper()}' MOTORCYCLES\n"
    result += "(Based on historical sales data 2020-2026)\n\n"
    result += f"Found {len(parts)} compatible parts:\n\n"
    
    result += "=" * 70 + "\n"
    result += "PART                    | BRAND    | PRICE      | SOLD\n"
    result += "=" * 70 + "\n"
    
    for p in parts[:25]:
        part_name = p.get("description", "N/A")[:24]
        brand = p.get("brand", "")[:8]
        qty = float(p.get("total_qty", 0) or 0)
        avg_price = float(p.get("avg_price", 0) or 0)
        result += f"{part_name:24s} | {brand:8s} | {format_ugx(avg_price):10s} | {qty:,.0f}\n"
    
    result += "=" * 70 + "\n"
    result += "\nNote: Prices are historical averages. Contact us for current pricing."
    result += "\nFor exact compatibility, please share your bike's full model name."
    
    return result


def build_models_list_response(models: List) -> str:
    """Build response showing all supported motorcycle models."""
    if not models:
        return "No motorcycle model data available."
    
    # Group models by brand
    bajaj = ["BM100KS", "BM100ES", "BM150", "CT125", "CT125-Old", "CT125/BM150", "Discover", "Pulsar", "Haojue-Xpress125"]
    hero = ["Hero-Hunter100", "Hero-Hunter125", "Hero-Hunter150", "Hero-Destini125", "Hero-Xpulse200", "Hero-HunterAll", "Hero-Hunter100/125", "Hero-Hunter100/150", "Hero-HunterAll/Destini125"]
    tvs = ["TVS HLX125", "TVS-HLX100", "TVS-HLX125", "TVS HLX-125", "TVS-HLX125/100", "TVS-VICTOR", "TVS Apache"]
    other = [m for m in models if m not in bajaj + hero + tvs]
    
    result = "SUPPORTED MOTORCYCLE MODELS\n\n"
    result += "We have parts for these popular motorcycles:\n\n"
    
    if bajaj:
        result += "BAJAJ:\n"
        result += ", ".join(sorted(set(bajaj))) + "\n\n"
    
    if hero:
        result += "HERO:\n"
        result += ", ".join(sorted(set(hero))) + "\n\n"
    
    if tvs:
        result += "TVS:\n"
        result += ", ".join(sorted(set(tvs))) + "\n\n"
    
    if other:
        result += "OTHER MODELS:\n"
        result += ", ".join(sorted(set(other))[:30])
        if len(other) > 30:
            result += f"\n...and {len(other) - 30} more models"
    
    result += "\n\nFor parts compatible with your bike, just ask: \"parts for BM100KS\" or \"clutch plate for Hero Hunter\""
    
    return result


def build_combined_items_response(combined_items: List, search: str, brand: str = None) -> str:
    """Build response combining items from ERPNext AND historical data."""
    erp_items = [i for i in combined_items if i.get("source") == "erpnext"]
    hist_items = [i for i in combined_items if i.get("source") == "historical"]
    
    result = f"SEARCH RESULTS FOR '{search.upper()}'\n"
    result += "(From ERPNext Database + Historical Records)\n\n"
    result += f"Total items found: {len(combined_items)}\n"
    result += f"  - ERPNext (current): {len(erp_items)} items\n"
    result += f"  - Historical (past sales): {len(hist_items)} items\n\n"
    
    if erp_items:
        result += "=" * 70 + "\n"
        result += "CURRENT STOCK (ERPNext)\n"
        result += "=" * 70 + "\n"
        for item in erp_items[:15]:
            name = item.get("item_name", "N/A")
            code = item.get("item_code", "N/A")
            item_brand = item.get("brand", "N/A")
            group = item.get("item_group", "N/A")
            rate = item.get("standard_rate", 0)
            result += f"• {name}\n"
            result += f"  Code: {code} | Brand: {item_brand}\n"
            if rate:
                result += f"  Price: {format_ugx(rate)}\n"
            result += "\n"
    
    if hist_items:
        result += "=" * 70 + "\n"
        result += "PAST SALES (Historical Data 2020-2026)\n"
        result += "=" * 70 + "\n"
        for item in hist_items[:15]:
            name = item.get("item_name", "N/A")
            item_brand = item.get("brand", "N/A")
            model = item.get("model", "")
            qty = float(item.get("qty_sold", 0) or 0)
            avg_price = float(item.get("avg_price", 0) or 0)
            result += f"• {name}\n"
            result += f"  Brand: {item_brand}"
            if model:
                result += f" | Model: {model}"
            result += "\n"
            result += f"  Qty Sold: {qty:,.0f}"
            if avg_price > 0:
                result += f" | Avg Price: {format_ugx(avg_price)}"
            result += "\n\n"
    
    if not combined_items:
        result += "No items found matching your search.\n"
        result += "Please try a different search term.\n"
    
    return result


def build_combined_prices_response(prices_data: List, search: str, brand: str = None) -> str:
    """Build response combining prices from ERPNext AND historical data."""
    erp_prices = [p for p in prices_data if p.get("source") == "erpnext"]
    hist_prices = [p for p in prices_data if p.get("source") == "historical"]
    
    result = f"PRICE RESULTS FOR '{search.upper()}'\n"
    result += "(From ERPNext Database + Historical Records)\n\n"
    result += f"Total entries found: {len(prices_data)}\n"
    result += f"  - ERPNext (current): {len(erp_prices)} items\n"
    result += f"  - Historical (past sales): {len(hist_prices)} entries\n\n"
    
    if erp_prices:
        result += "=" * 70 + "\n"
        result += "CURRENT PRICING (ERPNext)\n"
        result += "=" * 70 + "\n"
        for entry in erp_prices[:15]:
            item = entry.get("item", {})
            price = entry.get("price", {})
            name = item.get("item_name", "N/A")
            code = item.get("item_code", "N/A")
            rate = price.get("price_list_rate", 0) or 0
            currency = price.get("currency", "UGX")
            result += f"• {name}\n"
            result += f"  Code: {code} | Price: {rate:,.0f} {currency}\n\n"
    
    if hist_prices:
        result += "=" * 70 + "\n"
        result += "HISTORICAL PRICING (Past Sales 2020-2026)\n"
        result += "=" * 70 + "\n"
        for entry in hist_prices[:15]:
            item = entry.get("item", {})
            name = item.get("description", "N/A")
            item_brand = item.get("brand", "N/A")
            model = item.get("model", "")
            qty = float(item.get("item_qty", 0) or 0)
            sales = float(item.get("sales_amount", 0) or 0)
            if qty > 0:
                avg_price = sales / qty
                result += f"• {name}\n"
                result += f"  Brand: {item_brand}"
                if model:
                    result += f" | Model: {model}"
                result += f"\n  Last Sold: {qty:,.0f} units @ {format_ugx(avg_price)} avg\n\n"
    
    if not prices_data:
        result += "No pricing information found matching your search.\n"
        result += "Please try a different search term.\n"
    else:
        result += "\nNote: Historical prices are from past sales. Current prices may differ.\n"
        result += "Contact us for exact quotes and availability."
    
    return result


def build_historical_items_response(search: str, items: List) -> str:
    """Build response showing items from historical sales data."""
    # Aggregate by product
    products = {}
    for r in items:
        key = f"{r.get('description', '')} ({r.get('brand', '')})"
        if key not in products:
            products[key] = {
                "name": r.get("description", "N/A"),
                "brand": r.get("brand", ""),
                "model": r.get("model", ""),
                "hsn": r.get("hsn", ""),
                "count": 0,
                "total_qty": 0,
                "total_sales": 0,
                "prices": []
            }
        qty = float(r.get("item_qty", 0) or 0)
        sales = float(r.get("sales_amount", 0) or 0)
        if qty > 0:
            avg_price = sales / qty
            products[key]["prices"].append(avg_price)
            products[key]["total_qty"] += qty
            products[key]["total_sales"] += sales
            products[key]["count"] += 1
    
    result = f"PRODUCTS FOUND FOR '{search.upper()}'\n"
    result += "(Based on 2020-2026 sales data)\n\n"
    result += f"Found {len(products)} products matching '{search}':\n\n"
    result += "=" * 65 + "\n"
    result += "PRODUCT                    | BRAND   | PRICE      | SOLD\n"
    result += "=" * 65 + "\n"
    
    for key, p in list(products.items())[:20]:
        avg_price = sum(p["prices"]) / len(p["prices"]) if p["prices"] else 0
        brand = p["brand"][:8] if p["brand"] else "N/A"
        result += f"{key[:26]:26s} | {brand:8s} | {format_ugx(avg_price):10s} | {p['total_qty']:,.0f}\n"
    
    result += "=" * 65 + "\n"
    result += "\nNote: These are historical prices from past sales. Current prices may differ.\n"
    result += "For exact current pricing and availability, please contact us."
    
    return result
