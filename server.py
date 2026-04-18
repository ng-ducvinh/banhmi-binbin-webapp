#!/usr/bin/env python3
"""
Bánh Mì Bin Bin - Full E-Commerce Platform
Pure Python stdlib: http.server + sqlite3 + json
No pip dependencies required.
"""
import http.server, sqlite3, json, os, uuid, hashlib, hmac
from urllib.parse import urlparse, parse_qs, unquote_plus
from http.cookies import SimpleCookie
from datetime import datetime, timedelta
from functools import lru_cache
import html as html_escape_module

DB_PATH = os.path.join(os.path.dirname(__file__), 'banhmi.db')
SESSION_SECRET = 'bin-bin-secret-2024'
PORT = 5000

# ─── DB HELPERS ──────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def q(sql, params=(), one=False):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone() if one else cur.fetchall()

def ex(sql, params=()):
    with get_db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            phone TEXT, password_hash TEXT, role TEXT DEFAULT 'customer',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, slug TEXT UNIQUE, icon TEXT, sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, slug TEXT UNIQUE, description TEXT,
            price REAL, original_price REAL, category_id INTEGER,
            image_emoji TEXT DEFAULT '🥖', image_color TEXT DEFAULT '#f97316',
            stock INTEGER DEFAULT 100, is_featured INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1, rating REAL DEFAULT 4.8,
            review_count INTEGER DEFAULT 0, sold_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT UNIQUE, user_id INTEGER,
            guest_name TEXT, guest_phone TEXT, guest_email TEXT,
            shipping_address TEXT, status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'cod', payment_status TEXT DEFAULT 'unpaid',
            subtotal REAL DEFAULT 0, shipping_fee REAL DEFAULT 30000,
            discount REAL DEFAULT 0, total REAL DEFAULT 0,
            note TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER, product_id INTEGER,
            product_name TEXT, variant TEXT, quantity INTEGER DEFAULT 1,
            unit_price REAL, total_price REAL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER, user_id INTEGER, author_name TEXT,
            rating INTEGER DEFAULT 5, content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE, discount_type TEXT, discount_value REAL,
            min_order REAL DEFAULT 0, max_uses INTEGER DEFAULT 100,
            used_count INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, data TEXT, expires TEXT
        );
        """)
        conn.commit()

def seed_db():
    if q("SELECT id FROM categories LIMIT 1"):
        return
    cats = [
        ('Bánh Mì', 'banh-mi', '🥖', 1),
        ('Đồ Nguội', 'do-nguoi', '🥩', 2),
        ('Bánh Bao', 'banh-bao', '🥟', 3),
        ('Ăn Vặt', 'an-vat', '🍢', 4),
        ('Combo', 'combo', '🎁', 5),
        ('Xôi', 'xoi', '🍚', 6),
    ]
    for c in cats:
        ex("INSERT INTO categories(name,slug,icon,sort_order) VALUES(?,?,?,?)", c)
    cat_ids = {r['slug']:r['id'] for r in q("SELECT id,slug FROM categories")}
    products = [
        ('Bánh Mì Đặc Biệt','banh-mi-dac-biet','Bánh mì đặc biệt với đầy đủ nhân: pate, chả lụa, thịt nguội, dưa cải, rau thơm.',45000,50000,cat_ids['banh-mi'],'🥖','#c2410c',1,4.9,1250,15000),
        ('Bánh Mì Thịt Nướng','banh-mi-thit-nuong','Thịt nướng than hoa thơm phức, kết hợp với bánh mì giòn rụm.',40000,None,cat_ids['banh-mi'],'🍖','#b45309',1,4.8,890,8500),
        ('Bánh Mì Xíu Mại','banh-mi-xiu-mai','Xíu mại thịt heo đậm đà, nước sốt cà chua thơm ngon.',35000,None,cat_ids['banh-mi'],'🍱','#dc2626',0,4.7,560,5200),
        ('Bánh Mì Trứng','banh-mi-trung','Trứng ốp la tươi, kết hợp với các loại nhân phong phú.',30000,None,cat_ids['banh-mi'],'🍳','#d97706',0,4.6,420,4100),
        ('Bánh Mì Chay','banh-mi-chay','Bánh mì chay với các loại rau củ tươi ngon, phù hợp cho ngày chay.',25000,None,cat_ids['banh-mi'],'🥗','#16a34a',0,4.5,280,2800),
        ('Chả Lụa Bin Bin','cha-lua','Chả lụa cao cấp, được làm từ thịt heo tươi, bọc lá chuối truyền thống.',120000,140000,cat_ids['do-nguoi'],'🥩','#be185d',1,4.9,720,6500),
        ('Thịt Nguội Đặc Biệt','thit-nguoi','Thịt nguội cao cấp, hương vị đậm đà.',150000,None,cat_ids['do-nguoi'],'🍗','#9a3412',0,4.8,450,3800),
        ('Pate Gan','pate-gan','Pate gan heo thơm béo, được ủ theo công thức gia truyền.',85000,None,cat_ids['do-nguoi'],'🫙','#a16207',0,4.7,380,3200),
        ('Bánh Bao Nhân Thịt','banh-bao-thit','Bánh bao mềm, nhân thịt đậm đà, hấp nóng hổi.',20000,None,cat_ids['banh-bao'],'🥟','#f0abfc',1,4.7,650,7800),
        ('Bánh Bao Nhân Trứng','banh-bao-trung','Bánh bao với nhân trứng muối bùi béo đặc biệt.',18000,None,cat_ids['banh-bao'],'🥚','#fbbf24',0,4.6,420,5100),
        ('Nem Chua Rán','nem-chua-ran','Nem chua rán giòn rụm, chấm với tương ớt ngon tuyệt.',15000,None,cat_ids['an-vat'],'🍢','#f97316',0,4.6,890,12000),
        ('Chả Chiên','cha-chien','Chả chiên vàng giòn, hương thơm đặc trưng.',18000,None,cat_ids['an-vat'],'🍘','#c2410c',0,4.5,560,7200),
        ('Combo Gia Đình','combo-gia-dinh','4 bánh mì đặc biệt + 2 chả lụa, tiết kiệm hơn mua lẻ.',200000,250000,cat_ids['combo'],'🎁','#7c3aed',1,4.9,320,2100),
        ('Combo Sáng','combo-sang','2 bánh mì + 2 ly cà phê sữa, khởi đầu ngày mới tuyệt vời.',90000,110000,cat_ids['combo'],'☕','#92400e',1,4.8,180,1500),
    ]
    for p in products:
        ex("INSERT INTO products(name,slug,description,price,original_price,category_id,image_emoji,image_color,is_featured,rating,review_count,sold_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", p)
    # Admin
    pw = hashlib.sha256(('admin123'+SESSION_SECRET).encode()).hexdigest()
    ex("INSERT OR IGNORE INTO users(name,email,phone,password_hash,role) VALUES(?,?,?,?,?)",
       ('Admin Bin Bin','admin@binbin','0903351369',pw,'admin'))
    # Reviews
    for pid, name, rating, content in [(1,'Nguyễn Văn A',5,'Bánh mì ngon tuyệt vời! Nhân đầy đủ, bánh giòn tan.'),(1,'Trần Thị B',5,'Đây là bánh mì ngon nhất Sài Gòn tôi từng ăn!'),(2,'Lê Minh C',5,'Thịt nướng thơm, đậm đà, ăn là ghiền luôn.')]:
        ex("INSERT INTO reviews(product_id,author_name,rating,content) VALUES(?,?,?,?)", (pid,name,rating,content))
    # Coupons
    for code, dtype, val, minord, maxu in [('WELCOME10','percent',10,100000,500),('FREESHIP','fixed',30000,80000,1000),('VIP50K','fixed',50000,200000,100)]:
        ex("INSERT INTO coupons(code,discount_type,discount_value,min_order,max_uses) VALUES(?,?,?,?,?)", (code,dtype,val,minord,maxu))
    # Sample orders
    import random; random.seed(42)
    statuses = ['pending','confirmed','shipping','completed','completed','completed']
    for i in range(25):
        days = random.randint(0,30)
        dt = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        code = f'BM2024{1000+i:04d}'
        total = random.randint(2,8) * 45000 + 30000
        st = random.choice(statuses)
        oid = ex("INSERT INTO orders(order_code,guest_name,guest_phone,guest_email,shipping_address,status,payment_method,payment_status,subtotal,shipping_fee,total,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (code,f'Khách {i+1}',f'090{random.randint(1000000,9999999)}',f'kh{i+1}@gmail.com','123 Lê Lợi, Quận 1, TP.HCM',st,random.choice(['cod','banking','momo']),'paid' if random.random()>0.3 else 'unpaid',total-30000,30000,total,dt))
    print("✅ Database seeded!")

# ─── SESSIONS ────────────────────────────────────────────────────────────────

def get_session(sid):
    row = q("SELECT data,expires FROM sessions WHERE id=?", (sid,), one=True)
    if not row: return {}
    if datetime.fromisoformat(row['expires']) < datetime.now():
        ex("DELETE FROM sessions WHERE id=?", (sid,))
        return {}
    return json.loads(row['data'])

def save_session(sid, data):
    expires = (datetime.now() + timedelta(hours=24)).isoformat()
    ex("INSERT OR REPLACE INTO sessions(id,data,expires) VALUES(?,?,?)",
       (sid, json.dumps(data, ensure_ascii=False), expires))

def get_session_id(headers):
    cookie_str = headers.get('Cookie','')
    c = SimpleCookie(cookie_str)
    return c.get('sid', None) and c['sid'].value

def hash_pw(pw): return hashlib.sha256((pw+SESSION_SECRET).encode()).hexdigest()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fmt(n):
    try: return f"{int(n):,}đ".replace(",",".")
    except: return "0đ"

def e(s): return html_escape_module.escape(str(s) if s else '')

def discount_pct(price, orig):
    if orig and orig > price:
        return int((orig - price) / orig * 100)
    return 0

STATUS_LABELS = {
    'pending': ('Chờ xác nhận','#f59e0b'),
    'confirmed': ('Đã xác nhận','#3b82f6'),
    'shipping': ('Đang giao','#8b5cf6'),
    'completed': ('Hoàn thành','#10b981'),
    'cancelled': ('Đã hủy','#ef4444'),
}

# ─── HTML COMPONENTS ─────────────────────────────────────────────────────────

CSS = """
<style>
:root{--brand:#c2410c;--brand-dark:#9a3412;--brand-pale:#fff7ed;--gold:#b45309;--gold-light:#fef3c7;--text:#1c1917;--text-2:#57534e;--text-3:#a8a29e;--border:#e7e5e4;--bg:#fafaf9;--white:#fff;--success:#16a34a;--radius:12px;--shadow:0 1px 3px rgba(0,0,0,.08),0 4px 16px rgba(0,0,0,.06);--shadow-lg:0 8px 32px rgba(0,0,0,.12)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Be Vietnam Pro',sans-serif;background:var(--bg);color:var(--text);font-size:15px;line-height:1.6}
a{text-decoration:none;color:inherit}
button{cursor:pointer;font-family:inherit;border:none;background:none}
.navbar{position:sticky;top:0;z-index:100;background:rgba(255,255,255,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--border)}
.nav-inner{max-width:1280px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:20px;height:64px}
.nav-brand{display:flex;align-items:center;gap:10px;font-size:1.2rem;font-weight:800;color:var(--brand);letter-spacing:-.02em}
.nav-logo{width:36px;height:36px;background:var(--brand);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}
.nav-links{display:flex;gap:2px;flex:1;justify-content:center}
.nav-links a{padding:7px 13px;border-radius:8px;font-size:13px;font-weight:500;color:var(--text-2);transition:all .2s}
.nav-links a:hover,.nav-links a.active{color:var(--brand);background:var(--brand-pale)}
.nav-actions{display:flex;align-items:center;gap:8px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:8px;font-size:14px;font-weight:600;transition:all .2s;cursor:pointer;border:none;font-family:inherit}
.btn-primary{background:var(--brand);color:#fff}
.btn-primary:hover{background:var(--brand-dark);transform:translateY(-1px)}
.btn-secondary{background:transparent;color:var(--brand);border:1.5px solid var(--brand)}
.btn-secondary:hover{background:var(--brand-pale)}
.btn-sm{padding:6px 12px;font-size:12px}
.btn-nav{padding:7px 14px;border-radius:8px;font-size:13px;font-weight:500;transition:all .2s}
.btn-nav.outline{border:1.5px solid var(--border);color:var(--text-2)}
.btn-nav.outline:hover{border-color:var(--brand);color:var(--brand)}
.btn-nav.primary{background:var(--brand);color:#fff}
.cart-btn{position:relative;padding:8px 16px;border-radius:8px;background:var(--brand-pale);color:var(--brand);font-weight:600;font-size:13px;display:flex;align-items:center;gap:8px;transition:all .2s;cursor:pointer;border:none;font-family:inherit}
.cart-btn:hover{background:var(--brand);color:#fff}
.cart-badge{background:var(--brand);color:#fff;border-radius:50%;width:18px;height:18px;font-size:10px;display:inline-flex;align-items:center;justify-content:center;font-weight:700}
/* Cart sidebar */
.cart-overlay{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:200;opacity:0;pointer-events:none;transition:opacity .3s}
.cart-overlay.open{opacity:1;pointer-events:all}
.cart-sidebar{position:fixed;right:0;top:0;bottom:0;width:min(420px,100vw);background:#fff;z-index:201;transform:translateX(100%);transition:transform .3s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;box-shadow:var(--shadow-lg)}
.cart-sidebar.open{transform:translateX(0)}
.cart-header{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.cart-header h3{font-size:1.1rem;font-weight:700}
.cart-close{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:var(--text-2);font-size:20px;transition:all .2s;cursor:pointer;border:none;background:none}
.cart-close:hover{background:var(--border)}
.cart-body{flex:1;overflow-y:auto;padding:14px 20px}
.cart-empty{text-align:center;padding:60px 20px;color:var(--text-3)}
.cart-item{display:flex;gap:12px;padding:12px 0;border-bottom:1px solid var(--border)}
.cart-item-img{width:52px;height:52px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:26px;flex-shrink:0}
.cart-item-info{flex:1;min-width:0}
.cart-item-name{font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cart-item-price{font-size:13px;color:var(--brand);font-weight:600;margin-top:2px}
.cart-item-controls{display:flex;align-items:center;gap:8px;margin-top:6px}
.qty-btn{width:26px;height:26px;border-radius:6px;border:1.5px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;transition:all .2s;cursor:pointer;background:none}
.qty-btn:hover{border-color:var(--brand);color:var(--brand)}
.cart-footer{padding:14px 20px;border-top:1px solid var(--border)}
.cart-row{display:flex;justify-content:space-between;font-size:13px;padding:3px 0}
.cart-row.total{font-size:15px;font-weight:700;color:var(--brand);padding-top:8px;border-top:1px solid var(--border);margin-top:6px}
.coupon-row{display:flex;gap:8px;margin-bottom:10px}
.coupon-row input{flex:1;padding:8px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none}
.coupon-row button{padding:8px 14px;background:var(--brand);color:#fff;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:none;font-family:inherit}
.btn-checkout{width:100%;padding:13px;background:var(--brand);color:#fff;border-radius:10px;font-size:15px;font-weight:600;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer;border:none;font-family:inherit}
.btn-checkout:hover{background:var(--brand-dark)}
/* toast */
#toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--text);color:#fff;padding:10px 22px;border-radius:24px;font-size:14px;z-index:400;opacity:0;transition:all .3s;pointer-events:none;white-space:nowrap}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
/* product card */
.product-card{background:#fff;border-radius:var(--radius);border:1px solid var(--border);overflow:hidden;transition:all .25s;cursor:pointer}
.product-card:hover{transform:translateY(-4px);box-shadow:var(--shadow-lg);border-color:#fed7aa}
.product-img{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:64px;position:relative}
.product-badges{position:absolute;top:10px;left:10px;display:flex;flex-direction:column;gap:4px}
.badge{display:inline-flex;align-items:center;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700}
.badge-hot{background:#fee2e2;color:#dc2626}
.badge-sale{background:var(--gold-light);color:var(--gold)}
.product-info{padding:14px}
.product-name{font-size:13px;font-weight:600;margin-bottom:4px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.product-meta{font-size:11px;color:var(--text-3);margin-bottom:8px}
.price-current{font-size:15px;font-weight:700;color:var(--brand)}
.price-original{font-size:12px;color:var(--text-3);text-decoration:line-through;margin-left:6px}
.add-to-cart{margin-top:10px;width:100%;padding:8px;background:var(--brand-pale);color:var(--brand);border-radius:8px;font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center;gap:5px;transition:all .2s;cursor:pointer;border:none;font-family:inherit}
.add-to-cart:hover{background:var(--brand);color:#fff}
.grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.container{max-width:1280px;margin:0 auto;padding:0 20px}
.section{padding:60px 0}
.section-header{text-align:center;margin-bottom:36px}
.section-header h2{font-size:1.9rem;font-weight:800;margin-bottom:8px;letter-spacing:-.03em}
.page-hero{background:linear-gradient(135deg,#fff7ed,#fef3c7);padding:36px 0;margin-bottom:28px}
.page-hero h1{font-size:1.8rem;font-weight:800;color:var(--brand-dark)}
.breadcrumb{font-size:12px;color:var(--text-3);margin-bottom:6px}
footer{background:var(--text);color:#d6d3d1;padding:48px 20px 24px}
.footer-inner{max-width:1280px;margin:0 auto;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:40px;margin-bottom:36px}
.footer-col h4{color:#fff;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:12px}
.footer-col a{display:block;font-size:13px;color:#a8a29e;padding:2px 0;transition:color .2s}
.footer-col a:hover{color:#fff}
.footer-bottom{border-top:1px solid #292524;padding-top:18px;display:flex;justify-content:space-between;font-size:12px;color:#78716c}
/* search */
.search-wrap{flex:0 0 240px;position:relative}
.search-wrap input{width:100%;padding:7px 34px 7px 13px;border:1.5px solid var(--border);border-radius:20px;font-size:13px;font-family:inherit;background:var(--bg);outline:none;transition:border .2s}
.search-wrap input:focus{border-color:var(--brand);background:#fff}
.search-results{position:absolute;top:calc(100% + 5px);left:0;right:0;background:#fff;border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-lg);z-index:300;display:none}
.search-results.show{display:block}
.search-item{padding:9px 14px;display:flex;align-items:center;gap:10px;cursor:pointer;transition:background .15s;text-decoration:none;color:var(--text)}
.search-item:hover{background:var(--brand-pale)}
@media(max-width:1024px){.grid-4{grid-template-columns:repeat(3,1fr)}}
@media(max-width:768px){.grid-4{grid-template-columns:repeat(2,1fr)}.grid-3{grid-template-columns:1fr}.nav-links,.search-wrap{display:none}.footer-inner{grid-template-columns:1fr 1fr}.cart-sidebar{width:100vw}}
@media(max-width:480px){.grid-4{grid-template-columns:1fr}}
</style>
"""

def base_layout(content, title="Bánh Mì Bin Bin", sess=None, cart=None):
    sess = sess or {}
    cart = cart or sess.get('cart', {})
    user = sess.get('user')
    categories = q("SELECT * FROM categories ORDER BY sort_order")
    cart_count = sum(v['qty'] for v in cart.values())
    cart_total_val = sum(v['price'] * v['qty'] for v in cart.values())

    cat_links = ''.join(f'<a href="/menu/{c["slug"]}">{c["icon"]} {e(c["name"])}</a>' for c in categories)
    foot_cats = ''.join(f'<a href="/menu/{c["slug"]}">{c["icon"]} {e(c["name"])}</a>' for c in categories)

    cart_items_html = ""
    if cart:
        for key, item in cart.items():
            safe_key = key.replace('"', '')
            cart_items_html += f"""
            <div class="cart-item" id="ci-{e(safe_key)}">
              <div class="cart-item-img" style="background:{e(item['color'])}22">{e(item['emoji'])}</div>
              <div class="cart-item-info">
                <div class="cart-item-name">{e(item['name'])}</div>
                <div class="cart-item-price">{fmt(item['price'])}</div>
                <div class="cart-item-controls">
                  <button class="qty-btn" onclick="updateCart('{safe_key}',{item['qty']-1})">−</button>
                  <span id="qv-{e(safe_key)}">{item['qty']}</span>
                  <button class="qty-btn" onclick="updateCart('{safe_key}',{item['qty']+1})">+</button>
                  <button onclick="removeCart('{safe_key}')" style="margin-left:auto;color:var(--text-3);background:none;border:none;cursor:pointer;font-size:16px">🗑</button>
                </div>
              </div>
            </div>"""
    else:
        cart_items_html = '<div class="cart-empty"><div style="font-size:48px;margin-bottom:8px">🛒</div><p>Giỏ hàng trống</p></div>'

    discount = sess.get('coupon_discount', 0)
    auth_buttons = ""
    if user:
        auth_buttons = f'<a href="/account" class="btn-nav outline">👤 {e(user["name"].split()[0])}</a>'
        if user.get('role') == 'admin':
            auth_buttons += '<a href="/admin" class="btn-nav outline" style="margin-left:6px">⚙️ Admin</a>'
        auth_buttons += '<a href="/logout" class="btn-nav outline" style="margin-left:6px">Đăng xuất</a>'
    else:
        auth_buttons = '<a href="/login" class="btn-nav outline">Đăng nhập</a><a href="/register" class="btn-nav primary" style="margin-left:6px">Đăng ký</a>'

    badge_html = f'<span class="cart-badge">{cart_count}</span>' if cart_count else ''

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Bánh Mì Bin Bin - Tiệm bánh mì nổi tiếng nhất Sài Gòn, hơn 10 năm hương vị">
<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
{CSS}
</head>
<body>
<nav class="navbar">
  <div class="nav-inner">
    <a href="/" class="nav-brand"><div class="nav-logo">🥖</div> Bin Bin.</a>
    <div class="nav-links">
      <a href="/">Trang Chủ</a>
      <a href="/menu">Thực Đơn</a>
      {cat_links}
      <a href="/order/track">Tra Cứu ĐH</a>
    </div>
    <div class="search-wrap" id="sw">
      <input id="si" placeholder="Tìm kiếm..." autocomplete="off" oninput="doSearch(this.value)">
      <span style="position:absolute;right:10px;top:50%;transform:translateY(-50%);color:var(--text-3)">🔍</span>
      <div class="search-results" id="sr"></div>
    </div>
    <div class="nav-actions">
      {auth_buttons}
      <button class="cart-btn" onclick="toggleCart()">🛒 {fmt(cart_total_val)} {badge_html}</button>
    </div>
  </div>
</nav>

<div class="cart-overlay" id="co" onclick="toggleCart()"></div>
<div class="cart-sidebar" id="cs">
  <div class="cart-header"><h3>🛒 Giỏ hàng</h3><button class="cart-close" onclick="toggleCart()">✕</button></div>
  <div class="cart-body" id="cb">{cart_items_html}</div>
  <div class="cart-footer">
    <div class="coupon-row">
      <input id="ci2" placeholder="Mã giảm giá..." style="text-transform:uppercase">
      <button onclick="applyCoupon()">Áp dụng</button>
    </div>
    <div id="cs2">
      <div class="cart-row"><span>Tạm tính</span><span id="cst">{fmt(cart_total_val)}</span></div>
      <div class="cart-row"><span>Phí giao hàng</span><span>30.000đ</span></div>
      {'<div class="cart-row" style="color:var(--success)"><span>Giảm giá</span><span>-'+fmt(discount)+'</span></div>' if discount else ''}
      <div class="cart-row total"><span>Tổng</span><span id="ctot">{fmt(cart_total_val+30000-discount)}</span></div>
    </div>
    <a href="/checkout" class="btn-checkout">Đặt hàng ngay →</a>
  </div>
</div>
<div id="toast"></div>

{content}

<footer>
  <div class="footer-inner">
    <div>
      <h3 style="color:#fff;font-size:1.2rem;font-weight:800;margin-bottom:8px">🥖 Bánh Mì Bin Bin</h3>
      <p style="font-size:13px;color:#a8a29e;line-height:1.7;max-width:240px">Tiệm bánh mì nổi tiếng nhất Sài Gòn, hơn 10 năm gìn giữ hương vị truyền thống.</p>
    </div>
    <div class="footer-col"><h4>Thực Đơn</h4>{foot_cats}</div>
    <div class="footer-col">
      <h4>Hỗ Trợ</h4>
      <a href="/order/track">Tra cứu đơn hàng</a>
      <a href="#">Chính sách giao hàng</a>
      <a href="#">Đổi trả & hoàn tiền</a>
      <a href="#">Liên hệ</a>
    </div>
    <div class="footer-col">
      <h4>Liên Hệ</h4>
      <a href="#">📍 120/29/17B7 Thích Quãng Đức, P4, Q.PN</a>
      <a href="#">📞 090 351369</a>
      <a href="#">⏰ 6:00 - 11:00</a>
      <a href="#">📦 Giao hàng trong khu vực TPHCM</a>
    </div>
  </div>
  <div class="footer-bottom"><span>© {datetime.now().year} Bánh Mì Bin Bin</span><span>Bộ Công Thương 🔒</span></div>
</footer>

<script>
const fmtP = n => new Intl.NumberFormat('vi-VN').format(Math.round(n)) + 'đ';
function toggleCart(){{document.getElementById('co').classList.toggle('open');document.getElementById('cs').classList.toggle('open');}}
function updateCart(key,qty){{fetch('/api/cart/update',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{key,quantity:qty}})}}).then(r=>r.json()).then(d=>{{refreshCartUI(d);if(d.items)refreshCartItems(d.items);if(qty<=0)document.getElementById('ci-'+key)?.remove();else{{const el=document.getElementById('qv-'+key);if(el)el.textContent=qty;}}if(d.count===0)document.getElementById('cb').innerHTML='<div class="cart-empty"><div style="font-size:48px">🛒</div><p>Giỏ hàng trống</p></div>';}});}}
function removeCart(key){{fetch('/api/cart/remove',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{key}})}}).then(r=>r.json()).then(d=>{{refreshCartUI(d);document.getElementById('ci-'+key)?.remove();if(d.count===0)document.getElementById('cb').innerHTML='<div class="cart-empty"><div style="font-size:48px">🛒</div><p>Giỏ hàng trống</p></div>';}}); }}
function refreshCartUI(d){{document.querySelector('.cart-btn').innerHTML='🛒 '+fmtP(d.total)+(d.count>0?'<span class="cart-badge">'+d.count+'</span>':'');document.getElementById('cst').textContent=fmtP(d.total);document.getElementById('ctot').textContent=fmtP(d.total+30000);}}
function addToCart(pid,name,price,emoji,color){{fetch('/api/cart/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:pid,quantity:1}})}}).then(r=>r.json()).then(d=>{{refreshCartUI(d);showToast('✓ Đã thêm vào giỏ hàng!');location.reload();}});}}
function applyCoupon(){{const c=document.getElementById('ci2').value.trim();if(!c)return;fetch('/api/coupon/apply',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{code:c}})}}).then(r=>r.json()).then(d=>{{showToast(d.message,d.success?'ok':'err');if(d.success)setTimeout(()=>location.reload(),800);}});}}
function showToast(msg,type){{const t=document.getElementById('toast');t.textContent=msg;t.style.background=type==='err'?'#ef4444':'#1c1917';t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500);}}
let st;
function doSearch(q){{clearTimeout(st);if(!q){{document.getElementById('sr').classList.remove('show');return;}}st=setTimeout(()=>fetch('/api/search?q='+encodeURIComponent(q)).then(r=>r.json()).then(items=>{{const sr=document.getElementById('sr');if(!items.length){{sr.classList.remove('show');return;}}sr.innerHTML=items.map(p=>`<a href="/product/${{p.slug}}" class="search-item"><span style="font-size:20px">${{p.emoji}}</span><div><div style="font-size:13px;font-weight:500">${{p.name}}</div><div style="font-size:12px;color:var(--brand)">${{fmtP(p.price)}}</div></div></a>`).join('');sr.classList.add('show');}}),300);}}
document.addEventListener('click',ev=>{{if(!document.getElementById('sw').contains(ev.target))document.getElementById('sr').classList.remove('show');}});
</script>
</body></html>"""

def product_card(p, show_cat=False):
    dp = discount_pct(p['price'], p['original_price'])
    badges = ""
    if p['is_featured']: badges += '<span class="badge badge-hot">🔥 Hot</span>'
    if dp: badges += f'<span class="badge badge-sale">-{dp}%</span>'
    cat_label = f'<div style="font-size:11px;color:var(--text-3);margin-bottom:3px">{e(p.get("cat_name",""))}</div>' if show_cat else ""
    orig_html = f'<span class="price-original">{fmt(p["original_price"])}</span>' if p['original_price'] else ""
    return f"""
<div class="product-card" onclick="location.href='/product/{e(p['slug'])}'">
  <div class="product-img" style="background:{e(p['image_color'])}18">
    <span>{e(p['image_emoji'])}</span>
    <div class="product-badges">{badges}</div>
  </div>
  <div class="product-info">
    {cat_label}
    <div class="product-name">{e(p['name'])}</div>
    <div class="product-meta">⭐ {p['rating']} ({p['review_count']} đánh giá) · {p['sold_count']} đã bán</div>
    <div><span class="price-current">{fmt(p['price'])}</span>{orig_html}</div>
    <button class="add-to-cart" onclick="event.stopPropagation();addToCart({p['id']},'{e(p['name'])}',{p['price']},'{e(p['image_emoji'])}','{e(p['image_color'])}')">🛒 Thêm vào giỏ</button>
  </div>
</div>"""

# ─── PAGES ───────────────────────────────────────────────────────────────────

def page_home(sess):
    featured = q("SELECT p.*,c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_featured=1 AND p.is_active=1 LIMIT 6")
    best = q("SELECT * FROM products WHERE is_active=1 ORDER BY sold_count DESC LIMIT 4")
    cats = q("SELECT * FROM categories ORDER BY sort_order")
    feat_cards = ''.join(product_card(dict(p)) for p in featured)
    cat_pills = ''.join(f'<a href="/menu/{c["slug"]}" style="flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 18px;background:#fff;border:1.5px solid var(--border);border-radius:12px;transition:all .2s;min-width:80px;text-align:center" onmouseover="this.style.borderColor=\'var(--brand)\';this.style.background=\'var(--brand-pale)\'" onmouseout="this.style.borderColor=\'var(--border)\';this.style.background=\'#fff\'"><span style="font-size:26px">{e(c["icon"])}</span><span style="font-size:12px;font-weight:500;color:var(--text-2)">{e(c["name"])}</span></a>' for c in cats)
    best_list = ''.join(f'<a href="/product/{p["slug"]}" style="display:flex;align-items:center;gap:14px;padding:12px;background:var(--bg);border-radius:10px;border:1px solid var(--border);transition:all .2s" onmouseover="this.style.borderColor=\'var(--brand)\';this.style.background=\'var(--brand-pale)\'" onmouseout="this.style.borderColor=\'var(--border)\';this.style.background=\'var(--bg)\'"><div style="width:48px;height:48px;border-radius:9px;background:{e(p["image_color"])}18;display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0">{e(p["image_emoji"])}</div><div style="flex:1"><div style="font-weight:600;font-size:13px">{e(p["name"])}</div><div style="font-size:11px;color:var(--text-3)">Đã bán {p["sold_count"]}+ · ⭐ {p["rating"]}</div></div><div style="font-weight:700;color:var(--brand);font-size:13px">{fmt(p["price"])}</div></a>' for p in best)

    body = f"""
<section style="background:linear-gradient(135deg,#fff7ed 0%,#fef3c7 50%,#fff7ed 100%);padding:72px 0 56px;overflow:hidden">
  <div class="container" style="display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:center">
    <div>
      <div style="display:inline-flex;align-items:center;gap:8px;background:#fff;border:1px solid #fed7aa;border-radius:20px;padding:5px 14px;font-size:12px;color:var(--brand);font-weight:600;margin-bottom:18px">⭐ Hơn 10 năm phục vụ tại Sài Gòn</div>
      <h1 style="font-size:3rem;font-weight:800;line-height:1.1;letter-spacing:-.04em;margin-bottom:18px">Hương vị<br><span style="color:var(--brand)">truyền thống</span><br>giữa lòng Sài Gòn</h1>
      <p style="font-size:15px;color:var(--text-2);line-height:1.8;max-width:420px;margin-bottom:28px">Mỗi ổ bánh mì Bin Bin là sự kết hợp hoàn hảo giữa bánh mì giòn rụm, nhân đặc biệt đậm đà và hương thơm đặc trưng không nơi nào có.</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <a href="/menu" class="btn btn-primary" style="padding:13px 26px;font-size:14px">🛒 Đặt hàng ngay</a>
        <a href="/menu/banh-mi" class="btn btn-secondary" style="padding:13px 26px;font-size:14px">📋 Xem thực đơn</a>
      </div>
      <div style="display:flex;gap:28px;margin-top:36px">
        <div><div style="font-size:1.7rem;font-weight:800;color:var(--brand)">10+</div><div style="font-size:12px;color:var(--text-3)">Năm kinh nghiệm</div></div>
        <div><div style="font-size:1.7rem;font-weight:800;color:var(--brand)">20K+</div><div style="font-size:12px;color:var(--text-3)">Khách hàng</div></div>
        <div><div style="font-size:1.7rem;font-weight:800;color:var(--brand)">4.9⭐</div><div style="font-size:12px;color:var(--text-3)">Đánh giá</div></div>
      </div>
    </div>
    <div style="position:relative">
      <div style="background:#fff;border-radius:24px;padding:28px;box-shadow:0 20px 60px rgba(194,65,12,.15);text-align:center">
        <div style="font-size:110px;line-height:1">🥖</div>
        <h3 style="font-size:1.2rem;font-weight:700;margin:12px 0 5px">Bánh Mì Que</h3>
        <p style="font-size:12px;color:var(--text-3);margin-bottom:12px">Nhân đầy đủ · Bánh giòn · Hương thơm</p>
        <div style="font-size:1.4rem;font-weight:800;color:var(--brand)">12.000đ</div>
        <button onclick="addToCart(1,'Bánh Mì Que',12000,'🥖','#c2410c')" class="btn btn-primary" style="margin-top:12px;width:100%;justify-content:center">Thêm vào giỏ</button>
      </div>
      <div style="position:absolute;top:-10px;right:-10px;background:#fff;border-radius:10px;padding:7px 13px;box-shadow:var(--shadow);font-size:11px;font-weight:700;color:var(--success)">✓ Giao hàng nhanh</div>
      <div style="position:absolute;bottom:0;left:-20px;background:#fff;border-radius:10px;padding:7px 13px;box-shadow:var(--shadow);font-size:11px;font-weight:700;color:var(--brand)">🏆 #1 Sài Gòn</div>
    </div>
  </div>
</section>

<section style="padding:32px 0">
  <div class="container"><div style="display:flex;gap:10px;overflow-x:auto;padding-bottom:4px"><a href="/menu" style="flex-shrink:0;display:flex;flex-direction:column;align-items:center;gap:6px;padding:14px 18px;background:#fff;border:1.5px solid var(--brand);background:var(--brand-pale);border-radius:12px;min-width:80px;text-align:center"><span style="font-size:26px">🍽️</span><span style="font-size:12px;font-weight:600;color:var(--brand)">Tất cả</span></a>{cat_pills}</div></div>
</section>

<section class="section"><div class="container">
  <div class="section-header"><h2>Món Nổi Bật 🔥</h2><p>Những món được yêu thích nhất của chúng tôi</p></div>
  <div class="grid-4">{feat_cards}</div>
  <div style="text-align:center;margin-top:28px"><a href="/menu" class="btn btn-secondary">Xem tất cả thực đơn →</a></div>
</div></section>

<section class="section" style="background:#fff;padding:56px 0">
  <div class="container">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center">
      <div>
        <div style="font-size:11px;font-weight:700;color:var(--brand);text-transform:uppercase;letter-spacing:.12em;margin-bottom:7px">Bán Chạy Nhất</div>
        <h2 style="font-size:2rem;font-weight:800;letter-spacing:-.04em;margin-bottom:14px">Được khách hàng<br>tin yêu nhất</h2>
        <p style="color:var(--text-2);line-height:1.8;margin-bottom:22px;font-size:14px">Những sản phẩm đã chinh phục hàng triệu khách hàng với hương vị đặc trưng, chất lượng nhất quán.</p>
        <a href="/menu" class="btn btn-primary">Khám phá thêm →</a>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px">{best_list}</div>
    </div>
  </div>
</section>

<section style="background:var(--brand);padding:60px 0;color:#fff;text-align:center">
  <div class="container">
    <div style="font-size:44px;margin-bottom:14px">🏆</div>
    <h2 style="font-size:2.2rem;font-weight:800;margin-bottom:12px;letter-spacing:-.03em">Tiệm Bánh Mì Bin Bin</h2>
    <p style="font-size:14px;opacity:.9;max-width:560px;margin:0 auto 24px;line-height:1.8">Hơn 10 năm gìn giữ hương vị truyền thống, được báo chí quốc tế vinh danh là một trong những tiệm bánh mì ngon nhất Việt Nam.</p>
    <a href="/menu" style="display:inline-flex;align-items:center;gap:8px;background:#fff;color:var(--brand);padding:13px 28px;border-radius:10px;font-weight:700;font-size:14px;transition:all .2s">🥖 Đặt hàng ngay</a>
  </div>
</section>

<section style="background:var(--brand-pale);padding:44px 0">
  <div class="container">
    <div class="grid-4">
      {''.join(f'<div style="text-align:center;padding:22px;background:#fff;border-radius:12px"><div style="font-size:34px;margin-bottom:8px">{ic}</div><h4 style="font-weight:700;margin-bottom:5px;font-size:14px">{ti}</h4><p style="font-size:12px;color:var(--text-2)">{ds}</p></div>' for ic,ti,ds in [('🚀','Giao hàng nhanh','Trong 2-4h tại TP.HCM'),('❄️','Đóng gói cẩn thận','Giao đông lạnh toàn quốc'),('✅','Chất lượng đảm bảo','Hoàn tiền nếu không hài lòng'),('📞','Hỗ trợ 24/7','Hotline & Chat trực tuyến')])}
    </div>
  </div>
</section>
"""
    return base_layout(body, "Bánh Mì Bin Bin - Tiệm Bánh Mì Nổi Tiếng Nhất Sài Gòn", sess)

def page_menu(slug=None, sort='popular', search='', sess=None):
    sql = "SELECT p.*,c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.is_active=1"
    params = []
    active_cat = None
    if slug:
        active_cat = q("SELECT * FROM categories WHERE slug=?", (slug,), one=True)
        if active_cat:
            sql += " AND p.category_id=?"
            params.append(active_cat['id'])
    if search:
        sql += " AND p.name LIKE ?"
        params.append(f'%{search}%')
    if sort == 'price_asc': sql += " ORDER BY p.price ASC"
    elif sort == 'price_desc': sql += " ORDER BY p.price DESC"
    elif sort == 'newest': sql += " ORDER BY p.created_at DESC"
    else: sql += " ORDER BY p.sold_count DESC"
    products = q(sql, params)

    cats = q("SELECT * FROM categories ORDER BY sort_order")
    cat_tabs = '<a href="/menu" class="btn btn-sm ' + ('btn-primary' if not slug else 'btn-secondary') + '">Tất cả</a>'
    for c in cats:
        active = slug and active_cat and c['id'] == active_cat['id']
        cat_tabs += f'<a href="/menu/{c["slug"]}" class="btn btn-sm {"btn-primary" if active else "btn-secondary"}" style="flex-shrink:0">{e(c["icon"])} {e(c["name"])}</a>'

    sort_opts = ''
    for v, l in [('popular','Phổ biến nhất'),('newest','Mới nhất'),('price_asc','Giá tăng dần'),('price_desc','Giá giảm dần')]:
        sort_opts += f'<option value="?sort={v}" {"selected" if sort==v else ""}>{l}</option>'

    if products:
        cards = ''.join(product_card(dict(p), show_cat=True) for p in products)
        grid = f'<div class="grid-4">{cards}</div>'
    else:
        grid = '<div style="text-align:center;padding:80px 20px;color:var(--text-3)"><div style="font-size:56px;margin-bottom:14px">😕</div><h3>Không tìm thấy sản phẩm</h3><a href="/menu" class="btn btn-primary" style="margin-top:16px">Xem tất cả</a></div>'

    title_text = active_cat["icon"] + " " + active_cat["name"] if active_cat else "🍽️ Thực Đơn"
    body = f"""
<div class="page-hero">
  <div class="container">
    <div class="breadcrumb"><a href="/">Trang chủ</a> / <span>Thực đơn{" / "+e(active_cat["name"]) if active_cat else ""}</span></div>
    <h1>{e(title_text)}</h1>
    <p style="color:var(--text-2);margin-top:5px">{len(products)} sản phẩm</p>
  </div>
</div>
<div class="container" style="padding-bottom:64px">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:22px;flex-wrap:wrap">
    <div style="display:flex;gap:8px;overflow-x:auto;padding-bottom:4px">{cat_tabs}</div>
    <select onchange="location.href=this.value" style="padding:7px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none;cursor:pointer">{sort_opts}</select>
  </div>
  {grid}
</div>"""
    return base_layout(body, f'{""+active_cat["name"] if active_cat else "Thực Đơn"} - Bánh Mì Bin Bin', sess)

def page_product(slug, sess):
    p = q("SELECT p.*,c.name as cat_name,c.slug as cat_slug FROM products p LEFT JOIN categories c ON p.category_id=c.id WHERE p.slug=?", (slug,), one=True)
    if not p: return None
    p = dict(p)
    reviews = q("SELECT * FROM reviews WHERE product_id=? ORDER BY created_at DESC LIMIT 10", (p['id'],))
    related = q("SELECT * FROM products WHERE category_id=? AND id!=? AND is_active=1 LIMIT 4", (p['category_id'], p['id']))
    dp = discount_pct(p['price'], p['original_price'])
    stars_html = ''.join(f'<span style="color:{"#f59e0b" if i<int(p["rating"]) else "#d6d3d1"}">★</span>' for i in range(5))
    orig_html = f'<span style="font-size:1.1rem;color:var(--text-3);text-decoration:line-through;margin-left:10px">{fmt(p["original_price"])}</span><span class="badge badge-sale" style="margin-left:8px">-{dp}%</span>' if p['original_price'] else ''
    reviews_html = ''.join(f'<div style="padding:14px 18px;background:#fff;border:1px solid var(--border);border-radius:10px"><div style="display:flex;align-items:center;gap:10px;margin-bottom:7px"><div style="width:34px;height:34px;border-radius:50%;background:var(--brand-pale);display:flex;align-items:center;justify-content:center;font-weight:700;color:var(--brand);font-size:13px">{e(r["author_name"][0])}</div><div><div style="font-weight:600;font-size:13px">{e(r["author_name"])}</div><div style="color:#f59e0b;font-size:12px">{"★"*r["rating"]}</div></div><span style="margin-left:auto;font-size:11px;color:var(--text-3)">{r["created_at"][:10]}</span></div><p style="font-size:13px;color:var(--text-2)">{e(r["content"])}</p></div>' for r in reviews)
    related_html = ''.join(product_card(dict(rp)) for rp in related)

    body = f"""
<div class="container" style="padding:36px 0 64px">
  <div class="breadcrumb" style="margin-bottom:22px"><a href="/">Trang chủ</a> / <a href="/menu">Thực đơn</a> / <a href="/menu/{e(p.get("cat_slug",""))}">{e(p.get("cat_name",""))}</a> / {e(p["name"])}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start">
    <div style="background:{e(p["image_color"])}18;border-radius:20px;aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:140px;position:relative">
      {e(p["image_emoji"])}
      {"<div style='position:absolute;top:14px;left:14px' class='badge badge-hot'>🔥 Bán chạy</div>" if p["is_featured"] else ""}
    </div>
    <div>
      <div style="font-size:12px;color:var(--text-3);margin-bottom:5px">{e(p.get("cat_name",""))}</div>
      <h1 style="font-size:1.9rem;font-weight:800;letter-spacing:-.03em;margin-bottom:12px">{e(p["name"])}</h1>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">{stars_html}<span style="font-weight:600">{p["rating"]}</span><span style="color:var(--text-3);font-size:13px">({p["review_count"]} đánh giá)</span><span style="color:var(--text-3);font-size:13px">· {p["sold_count"]} đã bán</span></div>
      <div style="display:flex;align-items:baseline;gap:0;margin-bottom:18px"><span style="font-size:2rem;font-weight:800;color:var(--brand)">{fmt(p["price"])}</span>{orig_html}</div>
      <p style="color:var(--text-2);line-height:1.8;margin-bottom:22px;font-size:14px">{e(p["description"])}</p>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:22px">
        <span style="font-size:13px;font-weight:600">Số lượng:</span>
        <div style="display:flex;align-items:center;border:1.5px solid var(--border);border-radius:10px;overflow:hidden">
          <button onclick="chgQty(-1)" style="width:38px;height:38px;font-size:17px;font-weight:500;background:none;border:none;cursor:pointer">−</button>
          <span id="qv" style="width:44px;text-align:center;font-size:14px;font-weight:700;border-left:1px solid var(--border);border-right:1px solid var(--border);line-height:38px">1</span>
          <button onclick="chgQty(1)" style="width:38px;height:38px;font-size:17px;font-weight:500;background:none;border:none;cursor:pointer">+</button>
        </div>
        <span style="font-size:12px;color:var(--text-3)">Còn {p["stock"]} sp</span>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button onclick="atcDetailed({p['id']},'{e(p['name'])}',{p['price']},'{e(p['image_emoji'])}','{e(p['image_color'])}')" class="btn btn-primary" style="flex:1;justify-content:center;padding:13px;font-size:14px">🛒 Thêm vào giỏ hàng</button>
        <a href="/checkout" class="btn btn-secondary" style="flex:1;justify-content:center;padding:13px;font-size:14px">⚡ Mua ngay</a>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px">
        {"".join(f'<div style="display:flex;align-items:center;gap:7px;padding:9px 11px;background:var(--bg);border-radius:8px;font-size:12px;color:var(--text-2)">{ic} {tx}</div>' for ic,tx in [('🚀','Giao hàng 2-4h'),('❄️','Đóng gói cẩn thận'),('✅','Đảm bảo chất lượng'),('🔄','Hoàn tiền dễ dàng')])}
      </div>
    </div>
  </div>

  <div style="margin-top:56px">
    <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:20px">Đánh Giá Khách Hàng</h2>
    <div style="display:grid;gap:12px;margin-bottom:28px">{reviews_html if reviews_html else "<p style='color:var(--text-3)'>Chưa có đánh giá nào.</p>"}</div>
    <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px">
      <h3 style="font-size:14px;font-weight:700;margin-bottom:14px">Viết đánh giá</h3>
      <div style="display:flex;gap:4px;font-size:24px;cursor:pointer;margin-bottom:12px" id="stars">{"".join(f'<span onclick="setR({i+1})" data-r="{i+1}" style="color:#d6d3d1;transition:color .15s">★</span>' for i in range(5))}</div>
      <input id="rn" placeholder="Tên của bạn" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;margin-bottom:9px;outline:none">
      <textarea id="rc" rows="3" placeholder="Chia sẻ trải nghiệm..." style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;outline:none"></textarea>
      <button onclick="submitR({p['id']})" class="btn btn-primary" style="margin-top:9px">Gửi đánh giá</button>
    </div>
  </div>

  {f'<div style="margin-top:56px"><h2 style="font-size:1.5rem;font-weight:800;margin-bottom:20px">Sản Phẩm Liên Quan</h2><div class="grid-4">{"".join(product_card(dict(rp)) for rp in related)}</div></div>' if related else ''}
</div>
<script>
let curQ=1,curR=5;
function chgQty(d){{curQ=Math.max(1,Math.min(10,curQ+d));document.getElementById('qv').textContent=curQ;}}
function setR(n){{curR=n;document.querySelectorAll('#stars span').forEach((s,i)=>s.style.color=i<n?'#f59e0b':'#d6d3d1');}}
function atcDetailed(pid,name,price,emoji,color){{fetch('/api/cart/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:pid,quantity:curQ}})}}).then(r=>r.json()).then(d=>{{showToast('✓ Đã thêm '+curQ+' sản phẩm!');setTimeout(()=>location.reload(),700);}});}}
function submitR(pid){{const name=document.getElementById('rn').value.trim(),content=document.getElementById('rc').value.trim();if(!name||!content){{showToast('Vui lòng điền đầy đủ!','err');return;}}fetch('/api/review/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{product_id:pid,name,rating:curR,content}})}}).then(r=>r.json()).then(d=>{{if(d.success){{showToast('Cảm ơn đánh giá! ❤️');document.getElementById('rn').value='';document.getElementById('rc').value='';}}}});}}
setR(5);
</script>
"""
    return base_layout(body, f'{e(p["name"])} - Bánh Mì Bin Bin', sess)

def page_checkout(sess):
    cart = sess.get('cart', {})
    if not cart:
        return 'redirect:/menu'
    discount = sess.get('coupon_discount', 0)
    coupon_code = sess.get('coupon_code', '')
    subtotal = sum(v['price']*v['qty'] for v in cart.values())
    shipping = 30000
    total = subtotal + shipping - discount
    items_html = ''
    for k, item in cart.items():
        items_html += f'<div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)"><div style="width:40px;height:40px;border-radius:8px;background:{e(item["color"])}18;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0">{e(item["emoji"])}</div><div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{e(item["name"])}</div><div style="font-size:11px;color:var(--text-3)">x{item["qty"]}</div></div><div style="font-size:13px;font-weight:600;color:var(--brand)">{fmt(item["price"]*item["qty"])}</div></div>'
    user = sess.get('user')
    user_name = user['name'] if user else ''
    user_phone = user.get('phone','') if user else ''
    user_email = user['email'] if user else ''
    districts = ['Quận 1','Quận 2','Quận 3','Quận 4','Quận 5','Quận 6','Quận 7','Quận 8','Quận 9','Quận 10','Quận 11','Quận 12','Bình Thạnh','Gò Vấp','Phú Nhuận','Tân Bình','Tân Phú','Bình Tân','Thủ Đức','Nhà Bè','Bình Chánh','Hóc Môn','Củ Chi']
    district_opts = ''.join(f'<option value="{d}">{d}</option>' for d in districts)
    disc_row = f'<div class="cart-row" style="color:var(--success)"><span>Giảm giá ({e(coupon_code)})</span><span>-{fmt(discount)}</span></div>' if discount else ''
    pay_opts = ''
    for val, icon, label, desc in [('cod','💵','Tiền mặt khi nhận hàng','Thanh toán khi nhận'),('banking','🏦','Chuyển khoản ngân hàng','VCB/TCB/MB Bank'),('momo','💜','Ví MoMo','Quét QR nhanh'),('vnpay','🔵','VNPay','Nhiều ngân hàng')]:
        pay_opts += f'<label style="display:flex;align-items:center;gap:12px;padding:11px 14px;border:1.5px solid var(--border);border-radius:8px;cursor:pointer;margin-bottom:8px;transition:border-color .2s"><input type="radio" name="payment_method" value="{val}" {"checked" if val=="cod" else ""}><span style="font-size:20px">{icon}</span><div><div style="font-weight:600;font-size:13px">{label}</div><div style="font-size:11px;color:var(--text-3)">{desc}</div></div></label>'

    body = f"""
<div class="container" style="padding:36px 0 64px;max-width:960px">
  <h1 style="font-size:1.8rem;font-weight:800;margin-bottom:28px">🛒 Đặt Hàng</h1>
  <form method="POST" action="/checkout">
    <div style="display:grid;grid-template-columns:1fr 320px;gap:28px;align-items:start">
      <div>
        <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px;margin-bottom:16px">
          <h3 style="font-size:14px;font-weight:700;margin-bottom:14px">📋 Thông Tin Liên Hệ</h3>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
            <div><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Họ tên *</label><input name="name" required value="{e(user_name)}" placeholder="Nguyễn Văn A" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
            <div><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Điện thoại *</label><input name="phone" required value="{e(user_phone)}" placeholder="0901234567" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
          </div>
          <div><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Email</label><input name="email" type="email" value="{e(user_email)}" placeholder="email@example.com" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
        </div>
        <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px;margin-bottom:16px">
          <h3 style="font-size:14px;font-weight:700;margin-bottom:14px">📍 Địa Chỉ Giao Hàng</h3>
          <div style="margin-bottom:12px"><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Địa chỉ *</label><input name="address" required placeholder="Số nhà, tên đường" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Quận/Huyện *</label><select name="district" required style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"><option value="">Chọn quận...</option>{district_opts}</select></div>
            <div><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Thành phố *</label><select name="city" required style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"><option>TP. Hồ Chí Minh</option><option>Hà Nội</option><option>Đà Nẵng</option><option>Khác</option></select></div>
          </div>
        </div>
        <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px;margin-bottom:16px">
          <h3 style="font-size:14px;font-weight:700;margin-bottom:14px">💳 Phương Thức Thanh Toán</h3>
          {pay_opts}
        </div>
        <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px">
          <h3 style="font-size:14px;font-weight:700;margin-bottom:10px">📝 Ghi Chú</h3>
          <textarea name="note" placeholder="Ghi chú đặc biệt..." rows="3" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;resize:vertical;outline:none"></textarea>
        </div>
      </div>
      <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:22px;position:sticky;top:80px">
        <h3 style="font-size:14px;font-weight:700;margin-bottom:14px">📦 Đơn Hàng</h3>
        {items_html}
        <div style="margin-top:14px">
          <div class="cart-row"><span>Tạm tính</span><span>{fmt(subtotal)}</span></div>
          <div class="cart-row"><span>Phí giao hàng</span><span>{fmt(shipping)}</span></div>
          {disc_row}
          <div class="cart-row total"><span>Tổng cộng</span><span>{fmt(total)}</span></div>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;padding:13px;margin-top:14px;justify-content:center;font-size:14px;border-radius:10px">✓ Xác Nhận Đặt Hàng</button>
        <a href="/menu" style="display:block;text-align:center;font-size:12px;color:var(--text-3);margin-top:10px">← Tiếp tục mua hàng</a>
      </div>
    </div>
  </form>
</div>"""
    return base_layout(body, 'Đặt Hàng - Bánh Mì Bin Bin', sess)

def page_order_success(code, sess):
    order = q("SELECT * FROM orders WHERE order_code=?", (code,), one=True)
    if not order: return None
    st_label = STATUS_LABELS.get(order['status'],('',''))[0]
    pm_map = {'cod':'Tiền mặt COD','banking':'Chuyển khoản','momo':'MoMo','vnpay':'VNPay'}
    body = f"""
<div class="container" style="padding:80px 20px;max-width:560px;text-align:center">
  <div style="font-size:72px;margin-bottom:18px;animation:bounce .6s ease">✅</div>
  <h1 style="font-size:1.9rem;font-weight:800;color:var(--success);margin-bottom:10px">Đặt Hàng Thành Công!</h1>
  <p style="color:var(--text-2);margin-bottom:28px;font-size:14px">Cảm ơn bạn đã tin tưởng Bánh Mì Bin Bin.</p>
  <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:24px;text-align:left;margin-bottom:20px">
    <div style="display:flex;justify-content:space-between;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)"><span style="font-size:13px;color:var(--text-3)">Mã đơn hàng</span><span style="font-size:15px;font-weight:800;color:var(--brand);font-family:monospace">{e(order["order_code"])}</span></div>
    {"".join(f'<div style="display:flex;justify-content:space-between;font-size:13px;padding:5px 0"><span style="color:var(--text-3)">{l}</span><span style="font-weight:500;text-align:right">{e(str(v))}</span></div>' for l,v in [("Người nhận",order["guest_name"] or ""),("Điện thoại",order["guest_phone"] or ""),("Địa chỉ",order["shipping_address"] or ""),("Thanh toán",pm_map.get(order["payment_method"],""))])}
    <div style="display:flex;justify-content:space-between;font-size:15px;font-weight:800;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);color:var(--brand)"><span>Tổng cộng</span><span>{fmt(order["total"])}</span></div>
  </div>
  <div style="background:var(--brand-pale);border-radius:10px;padding:14px;margin-bottom:22px;font-size:13px;color:var(--brand-dark)">📞 Chúng tôi sẽ liên hệ xác nhận trong <strong>15 phút</strong></div>
  <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
    <a href="/order/track?code={e(code)}" class="btn btn-primary">📦 Theo dõi đơn hàng</a>
    <a href="/menu" class="btn btn-secondary">Tiếp tục mua hàng</a>
  </div>
</div>
<style>@keyframes bounce{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.12)}}}}</style>"""
    return base_layout(body, 'Đặt Hàng Thành Công - Bánh Mì Bin Bin', sess)

def page_order_track(code, sess):
    order = None
    if code:
        order = q("SELECT * FROM orders WHERE order_code=?", (code.upper(),), one=True)
    steps = [('pending','Đặt hàng'),('confirmed','Xác nhận'),('shipping','Đang giao'),('completed','Hoàn thành')]
    step_idx_map = {'pending':0,'confirmed':1,'shipping':2,'completed':3}
    if order:
        cur = step_idx_map.get(order['status'], 0)
        prog = ''
        for i,(sk,sl) in enumerate(steps):
            active = i <= cur
            if i > 0: prog += f'<div style="flex:1;height:3px;background:{"var(--brand)" if active else "var(--border)"}"></div>'
            prog += f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px"><div style="width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;background:{"var(--brand)" if active else "var(--border)"};color:{"#fff" if active else "var(--text-3)"}">{i+1}</div><span style="font-size:10px;color:{"var(--brand)" if active else "var(--text-3)"};white-space:nowrap">{sl}</span></div>'
        sl_label, sl_color = STATUS_LABELS.get(order['status'],('','#888'))
        pm_map = {'cod':'Tiền mặt COD','banking':'Chuyển khoản','momo':'MoMo'}
        result_html = f"""
<div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:24px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px"><div><div style="font-size:11px;color:var(--text-3);margin-bottom:3px">Mã đơn hàng</div><div style="font-size:1.2rem;font-weight:800;font-family:monospace;color:var(--brand)">{e(order["order_code"])}</div></div><span style="padding:5px 14px;border-radius:20px;font-size:12px;font-weight:700;background:{sl_color}18;color:{sl_color}">{e(sl_label)}</span></div>
  <div style="display:flex;align-items:center;gap:0;margin-bottom:24px">{prog}</div>
  {"".join(f'<div style="display:flex;justify-content:space-between;font-size:13px;padding:6px 0;border-bottom:1px solid var(--border)"><span style="color:var(--text-3)">{l}</span><span style="font-weight:500">{e(str(v))}</span></div>' for l,v in [("Ngày đặt",order["created_at"][:16]),("Người nhận",order["guest_name"] or ""),("Địa chỉ",order["shipping_address"] or ""),("Thanh toán",pm_map.get(order["payment_method"],""))])}
  <div style="display:flex;justify-content:space-between;font-size:15px;font-weight:800;margin-top:12px;color:var(--brand)"><span>Tổng cộng</span><span>{fmt(order["total"])}</span></div>
</div>"""
    elif code:
        result_html = f'<div style="text-align:center;padding:40px;background:#fff;border-radius:12px;border:1px solid var(--border)"><div style="font-size:48px;margin-bottom:12px">😕</div><p style="color:var(--text-2)">Không tìm thấy đơn hàng <strong>{e(code)}</strong></p></div>'
    else:
        result_html = ''

    body = f"""
<div class="container" style="padding:56px 0 64px;max-width:580px">
  <h1 style="font-size:1.8rem;font-weight:800;margin-bottom:22px;text-align:center">📦 Tra Cứu Đơn Hàng</h1>
  <form method="GET" action="/order/track" style="display:flex;gap:10px;margin-bottom:28px">
    <input name="code" value="{e(code)}" placeholder="Nhập mã đơn hàng (VD: BM20241A2B)" required style="flex:1;padding:11px 15px;border:1.5px solid var(--border);border-radius:10px;font-family:inherit;font-size:13px;outline:none">
    <button type="submit" class="btn btn-primary" style="padding:11px 18px">Tra Cứu</button>
  </form>
  {result_html}
</div>"""
    return base_layout(body, 'Tra Cứu Đơn Hàng - Bánh Mì Bin Bin', sess)

def page_login(sess, error=''):
    err_html = f'<div style="padding:10px 14px;background:#fee2e2;color:#dc2626;border-radius:8px;font-size:13px;margin-bottom:14px">✗ {e(error)}</div>' if error else ''
    body = f"""
<div style="min-height:60vh;display:flex;align-items:center;justify-content:center;padding:40px 20px">
  <div style="width:100%;max-width:400px">
    <div style="text-align:center;margin-bottom:28px"><div style="font-size:44px;margin-bottom:8px">🥖</div><h1 style="font-size:1.7rem;font-weight:800;letter-spacing:-.03em">Đăng Nhập</h1><p style="color:var(--text-3);font-size:13px;margin-top:5px">Chào mừng trở lại!</p></div>
    <form method="POST" action="/login" style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:26px">
      {err_html}
      <div style="margin-bottom:14px"><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Email</label><input name="email" type="email" required placeholder="email@example.com" style="width:100%;padding:10px 13px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
      <div style="margin-bottom:22px"><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">Mật khẩu</label><input name="password" type="password" required placeholder="••••••••" style="width:100%;padding:10px 13px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>
      <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;justify-content:center;font-size:14px;border-radius:9px">Đăng Nhập</button>
      <div style="text-align:center;margin-top:14px;font-size:13px;color:var(--text-3)">Chưa có tài khoản? <a href="/register" style="color:var(--brand);font-weight:600">Đăng ký ngay</a></div>
      <div style="text-align:center;margin-top:10px;font-size:11px;color:var(--text-3);padding:8px;background:var(--bg);border-radius:7px">Demo admin: admin@binbin / admin123</div>
    </form>
  </div>
</div>"""
    return base_layout(body, 'Đăng Nhập - Bánh Mì Bin Bin', sess)

def page_register(sess, error=''):
    err_html = f'<div style="padding:10px 14px;background:#fee2e2;color:#dc2626;border-radius:8px;font-size:13px;margin-bottom:14px">✗ {e(error)}</div>' if error else ''
    body = f"""
<div style="min-height:60vh;display:flex;align-items:center;justify-content:center;padding:40px 20px">
  <div style="width:100%;max-width:420px">
    <div style="text-align:center;margin-bottom:28px"><div style="font-size:44px;margin-bottom:8px">🥖</div><h1 style="font-size:1.7rem;font-weight:800;letter-spacing:-.03em">Tạo Tài Khoản</h1></div>
    <form method="POST" action="/register" style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:26px">
      {err_html}
      {"".join(f'<div style="margin-bottom:13px"><label style="font-size:12px;font-weight:600;display:block;margin-bottom:5px">{l}</label><input name="{n}" type="{t}" required placeholder="{ph}" style="width:100%;padding:10px 13px;border:1.5px solid var(--border);border-radius:8px;font-family:inherit;font-size:13px;outline:none"></div>' for n,t,l,ph in [('name','text','Họ tên *','Nguyễn Văn A'),('phone','tel','Số điện thoại *','0901234567'),('email','email','Email *','email@example.com'),('password','password','Mật khẩu *','Ít nhất 6 ký tự')])}
      <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;justify-content:center;font-size:14px;border-radius:9px;margin-top:6px">Đăng Ký</button>
      <div style="text-align:center;margin-top:14px;font-size:13px;color:var(--text-3)">Đã có tài khoản? <a href="/login" style="color:var(--brand);font-weight:600">Đăng nhập</a></div>
    </form>
  </div>
</div>"""
    return base_layout(body, 'Đăng Ký - Bánh Mì Bin Bin', sess)

def page_account(sess):
    user = sess.get('user')
    if not user: return 'redirect:/login'
    orders = q("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 15", (user['id'],))
    orders_html = ''
    if orders:
        for o in orders:
            sl, sc = STATUS_LABELS.get(o['status'],('','#888'))
            orders_html += f'<div style="background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin-bottom:10px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><span style="font-family:monospace;font-weight:800;color:var(--brand);font-size:14px">{e(o["order_code"])}</span><span style="padding:3px 12px;border-radius:20px;font-size:11px;font-weight:700;background:{sc}18;color:{sc}">{e(sl)}</span></div><div style="display:flex;justify-content:space-between;align-items:center"><div style="font-size:12px;color:var(--text-2)">{o["created_at"][:10]} · {"COD" if o["payment_method"]=="cod" else o["payment_method"].upper()}</div><div style="font-weight:800;color:var(--brand);font-size:14px">{fmt(o["total"])}</div></div><a href="/order/track?code={e(o["order_code"])}" style="font-size:12px;color:var(--brand);font-weight:600;margin-top:7px;display:block">Theo dõi đơn →</a></div>'
    else:
        orders_html = '<div style="text-align:center;padding:48px;background:#fff;border:1px solid var(--border);border-radius:12px"><div style="font-size:44px;margin-bottom:12px">📦</div><p style="color:var(--text-2);margin-bottom:14px">Chưa có đơn hàng nào</p><a href="/menu" class="btn btn-primary">Đặt hàng ngay</a></div>'

    body = f"""
<div class="container" style="padding:36px 0 64px">
  <div style="display:grid;grid-template-columns:220px 1fr;gap:28px;align-items:start">
    <div style="background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px">
      <div style="text-align:center;padding-bottom:14px;border-bottom:1px solid var(--border);margin-bottom:14px"><div style="width:60px;height:60px;border-radius:50%;background:var(--brand-pale);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:var(--brand);margin:0 auto 7px">{e(user["name"][0])}</div><div style="font-weight:700;font-size:14px">{e(user["name"])}</div><div style="font-size:11px;color:var(--text-3)">{e(user["email"])}</div></div>
      {"".join(f'<a href="#" style="display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:8px;font-size:13px;color:var(--text-2);margin-bottom:2px;transition:all .2s" onmouseover="this.style.background=\'var(--brand-pale)\';this.style.color=\'var(--brand)\'" onmouseout="this.style.background=\'transparent\';this.style.color=\'var(--text-2)\'">{ic} {l}</a>' for ic,l in [('📦','Đơn hàng của tôi'),('👤','Thông tin tài khoản'),('📍','Sổ địa chỉ')])}
      <div style="border-top:1px solid var(--border);margin-top:10px;padding-top:10px"><a href="/logout" style="display:flex;align-items:center;gap:8px;padding:9px 11px;border-radius:8px;font-size:13px;color:#ef4444;transition:background .2s" onmouseover="this.style.background=\'#fee2e2\'" onmouseout="this.style.background=\'transparent\'">🚪 Đăng xuất</a></div>
    </div>
    <div>
      <h1 style="font-size:1.7rem;font-weight:800;margin-bottom:20px">Đơn Hàng Của Tôi</h1>
      {orders_html}
    </div>
  </div>
</div>"""
    return base_layout(body, 'Tài Khoản - Bánh Mì Bin Bin', sess)

# ─── ADMIN PAGES ─────────────────────────────────────────────────────────────

ADMIN_CSS = """<style>
body{font-family:'Be Vietnam Pro',sans-serif;margin:0;background:#fafaf9;color:#1c1917;display:flex;min-height:100vh}
a{text-decoration:none;color:inherit}
.sidebar{width:220px;background:#1c1917;min-height:100vh;position:sticky;top:0;flex-shrink:0;display:flex;flex-direction:column}
.sb-brand{padding:18px 16px;border-bottom:1px solid #292524}
.sb-brand h2{color:#fff;font-size:14px;font-weight:800}
.sb-brand span{font-size:11px;color:#78716c;display:block;margin-top:2px}
.sb-nav{flex:1;padding:10px 8px}
.sb-sec{font-size:10px;font-weight:700;color:#78716c;text-transform:uppercase;letter-spacing:.1em;padding:10px 8px 4px}
.sb-item{display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;font-size:13px;color:#a8a29e;margin-bottom:2px;transition:all .2s}
.sb-item:hover,.sb-item.active{background:#292524;color:#fff}
.sb-bottom{padding:10px 8px;border-top:1px solid #292524}
.main{flex:1;min-width:0;display:flex;flex-direction:column}
.topbar{background:#fff;border-bottom:1px solid #e7e5e4;padding:0 22px;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}
.topbar h1{font-size:1rem;font-weight:800}
.content{padding:20px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:18px}
.metric{background:#fff;border:1px solid #e7e5e4;border-radius:12px;padding:18px 20px}
.metric .lbl{font-size:11px;font-weight:700;color:#a8a29e;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px}
.metric .val{font-size:1.6rem;font-weight:800;color:#1c1917}
.metric .dt{display:inline-flex;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:700;margin-top:5px;background:#dcfce7;color:#16a34a}
.card{background:#fff;border:1px solid #e7e5e4;border-radius:12px;overflow:hidden;margin-bottom:16px}
.card-head{padding:14px 18px;border-bottom:1px solid #e7e5e4;display:flex;align-items:center;justify-content:space-between}
.card-head h3{font-size:13px;font-weight:700}
table{width:100%;border-collapse:collapse}
th{font-size:11px;font-weight:700;color:#a8a29e;text-transform:uppercase;letter-spacing:.06em;padding:9px 14px;text-align:left;border-bottom:1px solid #e7e5e4;background:#fafaf9}
td{padding:10px 14px;border-bottom:1px solid #e7e5e4;font-size:13px;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fff7ed}
.s{display:inline-flex;padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700}
.s-pending{background:#fef3c7;color:#b45309}.s-confirmed{background:#dbeafe;color:#1d4ed8}
.s-shipping{background:#ede9fe;color:#7c3aed}.s-completed{background:#dcfce7;color:#16a34a}
.s-cancelled{background:#fee2e2;color:#dc2626}.s-paid{background:#dcfce7;color:#16a34a}.s-unpaid{background:#fee2e2;color:#dc2626}
.btn{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border-radius:7px;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s;border:none;font-family:inherit}
.btn-p{background:#c2410c;color:#fff}.btn-p:hover{background:#9a3412}
.btn-o{background:transparent;border:1px solid #e7e5e4;color:#57534e}.btn-o:hover{border-color:#c2410c;color:#c2410c}
.btn-s{background:#16a34a;color:#fff}.btn-d{background:#dc2626;color:#fff}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
input,select,textarea{font-family:'Be Vietnam Pro',sans-serif}
</style>"""

def admin_layout(content, title, page):
    user_name = 'Admin'
    pending = q("SELECT COUNT(*) as c FROM orders WHERE status='pending'", one=True)['c']
    pages = [('📊','Dashboard','/admin','dashboard'),('📦','Đơn hàng','/admin/orders','orders'),('🥖','Sản phẩm','/admin/products','products'),('👥','Khách hàng','/admin/customers','customers'),('🎟️','Mã giảm giá','/admin/coupons','coupons'),('📈','Báo cáo','/admin/reports','reports')]
    nav = ''.join(f'<a href="{url}" class="sb-item {"active" if p==page else ""}">{ic} {l}{(" <span style=background:#ef4444;color:#fff;border-radius:20px;padding:1px 6px;font-size:10px>"+str(pending)+"</span>") if p=="orders" and pending else ""}</a>' for ic,l,url,p in pages)
    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} - Admin Bin Bin</title>
<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800&display=swap" rel="stylesheet">
{ADMIN_CSS}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
<aside class="sidebar">
  <div class="sb-brand"><h2>🥖 Bin Bin</h2><span>Quản trị hệ thống</span></div>
  <nav class="sb-nav">
    <div class="sb-sec">Tổng quan</div>{nav[:nav.index('📦')].replace('sb-item','sb-item')}</nav>
  <nav class="sb-nav" style="padding-top:0">{nav[nav.index('📦'):]}</nav>
  <div class="sb-bottom">
    <a href="/" class="sb-item">🌐 Xem website</a>
    <a href="/logout" class="sb-item">🚪 Đăng xuất</a>
  </div>
</aside>
<div class="main">
  <div class="topbar"><h1>{e(title)}</h1><span style="font-size:12px;color:#a8a29e">Xin chào, <strong style="color:#1c1917">{e(user_name)}</strong></span></div>
  <div class="content">{content}</div>
</div>
<script>const fmtP=n=>new Intl.NumberFormat('vi-VN').format(Math.round(n))+'đ';</script>
</body></html>"""

def page_admin_dashboard():
    total_orders = q("SELECT COUNT(*) as c FROM orders", one=True)['c']
    total_revenue = q("SELECT COALESCE(SUM(total),0) as s FROM orders WHERE payment_status='paid'", one=True)['s']
    total_products = q("SELECT COUNT(*) as c FROM products WHERE is_active=1", one=True)['c']
    total_customers = q("SELECT COUNT(*) as c FROM users WHERE role='customer'", one=True)['c']
    pending = q("SELECT COUNT(*) as c FROM orders WHERE status='pending'", one=True)['c']
    recent = q("SELECT * FROM orders ORDER BY created_at DESC LIMIT 8")
    top_prods = q("SELECT * FROM products ORDER BY sold_count DESC LIMIT 5")
    rev_data = []
    for i in range(6,-1,-1):
        d = (datetime.now() - timedelta(days=i))
        ds = d.strftime('%Y-%m-%d')
        rev = q(f"SELECT COALESCE(SUM(total),0) as s FROM orders WHERE date(created_at)=? AND payment_status='paid'", (ds,), one=True)['s']
        rev_data.append({'date': d.strftime('%d/%m'), 'revenue': rev})

    metrics_html = ''
    for icon,label,val,delta in [('📦','Tổng đơn hàng',total_orders,'+12% tháng này'),('💰','Doanh thu (đã TT)',fmt(total_revenue),''),('🥖','Sản phẩm đang bán',total_products,'SKUs'),('👥','Khách hàng đăng ký',total_customers,'+8% tháng này')]:
        metrics_html += f'<div class="metric"><div class="lbl">{icon} {label}</div><div class="val">{val}</div><div class="dt">▲ {delta}</div></div>'

    pending_banner = f'<div style="padding:10px 16px;background:#fef3c7;border-bottom:1px solid #e7e5e4;font-size:13px;color:#b45309;display:flex;align-items:center;gap:8px">⚠️ <strong>{pending}</strong> đơn hàng chờ xác nhận <a href="/admin/orders?status=pending" style="color:#c2410c;font-weight:700;margin-left:auto">Xử lý ngay →</a></div>' if pending else ''
    orders_rows = ''
    for o in recent:
        sl, sc = STATUS_LABELS.get(o['status'],('','#888'))
        orders_rows += f'<tr><td><code style="font-family:monospace;color:#c2410c;font-size:11px">{e(o["order_code"])}</code></td><td><div style="font-weight:600">{e(o["guest_name"] or "")}</div><div style="font-size:11px;color:#a8a29e">{e(o["guest_phone"] or "")}</div></td><td style="font-weight:700;color:#c2410c">{fmt(o["total"])}</td><td><span class="s s-{o["status"]}">{e(sl)}</span></td><td style="font-size:11px;color:#a8a29e">{o["created_at"][:16]}</td></tr>'
    top_html = ''.join(f'<div style="display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid #e7e5e4"><span style="font-size:20px">{e(p["image_emoji"])}</span><div style="flex:1"><div style="font-size:13px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px">{e(p["name"])}</div><div style="font-size:11px;color:#a8a29e">{p["sold_count"]} đã bán</div></div><div style="font-weight:700;color:#c2410c;font-size:13px">{fmt(p["price"])}</div></div>' for p in top_prods)

    content = f"""
<div class="metrics">{metrics_html}</div>
<div class="grid2">
  <div class="card"><div class="card-head"><h3>📈 Doanh thu 7 ngày</h3></div><div style="padding:16px"><canvas id="rc" height="140"></canvas></div></div>
  <div class="card"><div class="card-head"><h3>🏆 Sản phẩm bán chạy</h3></div>{top_html}</div>
</div>
<div class="card">{pending_banner}<div class="card-head"><h3>📦 Đơn hàng gần đây</h3><a href="/admin/orders" class="btn btn-o">Xem tất cả →</a></div>
<table><thead><tr><th>Mã đơn</th><th>Khách hàng</th><th>Tổng tiền</th><th>Trạng thái</th><th>Ngày đặt</th></tr></thead><tbody>{orders_rows}</tbody></table></div>
<script>
const rd={json.dumps(rev_data)};
new Chart(document.getElementById('rc'),{{type:'bar',data:{{labels:rd.map(d=>d.date),datasets:[{{label:'Doanh thu',data:rd.map(d=>d.revenue),backgroundColor:'rgba(194,65,12,.15)',borderColor:'#c2410c',borderWidth:2,borderRadius:6}}]}},options:{{responsive:true,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:v=>fmtP(v.raw)}}}}}},scales:{{y:{{ticks:{{callback:v=>fmtP(v)}},grid:{{color:'rgba(0,0,0,.04)'}}}},x:{{grid:{{display:false}}}}}}}}}});
</script>"""
    return admin_layout(content, '📊 Dashboard', 'dashboard')

def page_admin_orders(status=''):
    sql = "SELECT * FROM orders"
    params = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    orders = q(sql, params)
    tabs = ''
    for sk, sl in [('','Tất cả'),('pending','Chờ xác nhận'),('confirmed','Đã xác nhận'),('shipping','Đang giao'),('completed','Hoàn thành'),('cancelled','Đã hủy')]:
        active = status == sk
        tabs += f'<a href="/admin/orders{"?status="+sk if sk else ""}" class="btn {"btn-p" if active else "btn-o"}">{sl}</a>'
    rows = ''
    for o in orders:
        sl, sc = STATUS_LABELS.get(o['status'],('','#888'))
        select_opts = ''.join(f'<option value="{sk}" {"selected" if o["status"]==sk else ""}>{sv[0]}</option>' for sk,sv in STATUS_LABELS.items())
        pm_map = {'cod':'COD','banking':'Chuyển khoản','momo':'MoMo','vnpay':'VNPay'}
        rows += f'<tr><td><code style="font-family:monospace;color:#c2410c;font-size:11px">{e(o["order_code"])}</code></td><td><div style="font-weight:600">{e(o["guest_name"] or "")}</div><div style="font-size:11px;color:#a8a29e">{e(o["guest_phone"] or "")} · {pm_map.get(o["payment_method"],"")}</div></td><td style="font-weight:700;color:#c2410c">{fmt(o["total"])}</td><td><span class="s s-{"paid" if o["payment_status"]=="paid" else "unpaid"}">{"✓ Đã TT" if o["payment_status"]=="paid" else "✗ Chưa TT"}</span></td><td><span class="s s-{o["status"]}">{e(sl)}</span></td><td style="font-size:11px;color:#a8a29e">{o["created_at"][:16]}</td><td><form method="POST" action="/admin/orders/{o["id"]}/update" style="display:inline-flex;gap:4px"><select name="status" style="padding:4px 8px;border:1px solid #e7e5e4;border-radius:6px;font-size:12px;font-family:inherit;outline:none">{select_opts}</select><button type="submit" class="btn btn-p">OK</button></form></td></tr>'
    content = f'<div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">{tabs}</div><div class="card"><div class="card-head"><h3>{len(orders)} đơn hàng</h3></div><table><thead><tr><th>Mã đơn</th><th>Khách hàng</th><th>Tổng tiền</th><th>TT Thanh toán</th><th>Trạng thái</th><th>Ngày đặt</th><th>Hành động</th></tr></thead><tbody>{rows}</tbody></table></div>'
    return admin_layout(content, '📦 Quản Lý Đơn Hàng', 'orders')

def page_admin_products():
    products = q("SELECT p.*,c.name as cat_name FROM products p LEFT JOIN categories c ON p.category_id=c.id ORDER BY c.sort_order,p.name")
    rows = ''
    for p in products:
        dp = discount_pct(p['price'],p['original_price'])
        orig = f'<div style="font-size:10px;color:#a8a29e;text-decoration:line-through">{fmt(p["original_price"])}</div>' if p['original_price'] else ''
        rows += f'<tr><td><div style="display:flex;align-items:center;gap:10px"><div style="width:38px;height:38px;border-radius:8px;background:{e(p["image_color"])}18;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0">{e(p["image_emoji"])}</div><div><div style="font-weight:600;font-size:13px">{e(p["name"])}</div><div style="font-size:10px;color:#a8a29e">/{e(p["slug"])}</div></div></div></td><td style="color:#57534e">{e(p["cat_name"] or "")}</td><td><strong style="color:#c2410c">{fmt(p["price"])}</strong>{orig}</td><td style="color:{"#dc2626" if p["stock"]<10 else "#1c1917"}">{p["stock"]}</td><td style="font-weight:600">{p["sold_count"]}</td><td>⭐ {p["rating"]} ({p["review_count"]})</td><td>{"<span class=s style=background:#dcfce7;color:#16a34a>Đang bán</span>" if p["is_active"] else "<span class=s style=background:#fee2e2;color:#dc2626>Ẩn</span>"}{"<span class=s style=background:#fef3c7;color:#b45309;margin-left:4px>Nổi bật</span>" if p["is_featured"] else ""}</td></tr>'
    content = f'<div style="display:flex;justify-content:flex-end;margin-bottom:14px"><a href="/admin/products/add" class="btn btn-p">+ Thêm sản phẩm</a></div><div class="card"><table><thead><tr><th>Sản phẩm</th><th>Danh mục</th><th>Giá</th><th>Tồn kho</th><th>Đã bán</th><th>Đánh giá</th><th>Trạng thái</th></tr></thead><tbody>{rows}</tbody></table></div>'
    return admin_layout(content, '🥖 Quản Lý Sản Phẩm', 'products')

def page_admin_product_add():
    cats = q("SELECT * FROM categories ORDER BY sort_order")
    cat_opts = ''.join(f'<option value="{c["id"]}">{e(c["name"])}</option>' for c in cats)
    form = f"""<div style="max-width:680px"><form method="POST" action="/admin/products/add"><div class="card" style="margin-bottom:14px"><div class="card-head"><h3>Thông tin sản phẩm</h3></div><div style="padding:18px;display:grid;gap:12px">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Tên (VI) *</label><input name="name" required style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Slug *</label><input name="slug" required placeholder="banh-mi-ten" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
    </div>
    <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Mô tả</label><textarea name="description" rows="3" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none;resize:vertical"></textarea></div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Giá bán *</label><input name="price" type="number" required placeholder="45000" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Giá gốc</label><input name="original_price" type="number" placeholder="50000" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Tồn kho</label><input name="stock" type="number" value="100" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 80px 100px;gap:12px">
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Danh mục *</label><select name="category_id" required style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none">{cat_opts}</select></div>
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Emoji</label><input name="image_emoji" value="🥖" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:16px;outline:none"></div>
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Màu nền</label><input name="image_color" type="color" value="#f97316" style="width:100%;height:36px;border:1px solid #e7e5e4;border-radius:7px;cursor:pointer;padding:2px"></div>
    </div>
    <label style="display:flex;align-items:center;gap:8px;cursor:pointer"><input type="checkbox" name="is_featured" style="width:15px;height:15px;accent-color:#c2410c"><span style="font-size:13px;font-weight:500">Sản phẩm nổi bật</span></label>
  </div></div>
  <div style="display:flex;gap:10px"><button type="submit" class="btn btn-p">💾 Lưu sản phẩm</button><a href="/admin/products" class="btn btn-o">Huỷ</a></div>
</form></div>"""
    return admin_layout(form, '➕ Thêm Sản Phẩm', 'products')

def page_admin_customers():
    customers = q("SELECT u.*,(SELECT COUNT(*) FROM orders WHERE user_id=u.id) as order_cnt FROM users WHERE role='customer' ORDER BY created_at DESC")
    rows = ''.join(f'<tr><td><div style="display:flex;align-items:center;gap:10px"><div style="width:34px;height:34px;border-radius:50%;background:#fff7ed;display:flex;align-items:center;justify-content:center;font-weight:800;color:#c2410c;font-size:13px;flex-shrink:0">{e(c["name"][0])}</div><div style="font-weight:600">{e(c["name"])}</div></div></td><td style="color:#57534e">{e(c["email"])}</td><td style="color:#57534e">{e(c["phone"] or "-")}</td><td><span style="font-weight:700">{c["order_cnt"]}</span> đơn</td><td style="font-size:11px;color:#a8a29e">{c["created_at"][:10]}</td></tr>' for c in customers)
    content = f'<div class="card"><div class="card-head"><h3>{len(customers)} khách hàng</h3></div><table><thead><tr><th>Tên</th><th>Email</th><th>Điện thoại</th><th>Đơn hàng</th><th>Ngày đăng ký</th></tr></thead><tbody>{rows}</tbody></table></div>'
    return admin_layout(content, '👥 Khách Hàng', 'customers')

def page_admin_reports():
    cat_rev = q("SELECT c.name,COALESCE(SUM(oi.total_price),0) as rev FROM categories c LEFT JOIN products p ON c.id=p.category_id LEFT JOIN order_items oi ON p.id=oi.product_id GROUP BY c.name ORDER BY rev DESC")
    monthly = []
    for i in range(5,-1,-1):
        m_start = (datetime.now().replace(day=1) - timedelta(days=30*i))
        m_str = m_start.strftime('%Y-%m')
        rev = q("SELECT COALESCE(SUM(total),0) as s FROM orders WHERE strftime('%Y-%m',created_at)=? AND status='completed'", (m_str,), one=True)['s']
        cnt = q("SELECT COUNT(*) as c FROM orders WHERE strftime('%Y-%m',created_at)=?", (m_str,), one=True)['c']
        monthly.append({'month': m_start.strftime('%m/%Y'), 'revenue': rev, 'orders': cnt})
    cat_labels = json.dumps([r['name'] for r in cat_rev])
    cat_vals   = json.dumps([r['rev']  for r in cat_rev])
    cat_rows = ''.join(
        '<tr><td style="font-weight:600">' + e(r['name']) + '</td>'
        '<td style="font-weight:700;color:#c2410c">' + fmt(r['rev']) + '</td></tr>'
        for r in cat_rev
    )
    md_json = json.dumps(monthly)
    script = (
        '<script>'
        'const md=' + md_json + ','
        "colors=['#c2410c','#b45309','#dc2626','#7c3aed','#0891b2'];"
        "const cl=" + cat_labels + ",cv=" + cat_vals + ";"
        "new Chart(document.getElementById('mc'),{type:'line',data:{labels:md.map(d=>d.month),datasets:[{label:'Doanh thu',data:md.map(d=>d.revenue),borderColor:'#c2410c',backgroundColor:'rgba(194,65,12,.08)',fill:true,tension:.4,pointRadius:4}]},options:{responsive:true,plugins:{legend:{display:false},tooltip:{callbacks:{label:v=>fmtP(v.raw)}}},scales:{y:{ticks:{callback:v=>fmtP(v)},grid:{color:'rgba(0,0,0,.04)'}},x:{grid:{display:false}}}}});"
        "new Chart(document.getElementById('oc'),{type:'bar',data:{labels:md.map(d=>d.month),datasets:[{label:'Don',data:md.map(d=>d.orders),backgroundColor:'rgba(180,83,9,.2)',borderColor:'#b45309',borderWidth:2,borderRadius:6}]},options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{grid:{color:'rgba(0,0,0,.04)'}},x:{grid:{display:false}}}}});"
        "new Chart(document.getElementById('cc'),{type:'doughnut',data:{labels:cl,datasets:[{data:cv,backgroundColor:colors,borderWidth:0}]},options:{responsive:true,plugins:{legend:{position:'bottom'},tooltip:{callbacks:{label:v=>v.label+': '+fmtP(v.raw)}}}}});"
        '</script>'
    )
    content = (
        '<div class="grid2">'
        '<div class="card"><div class="card-head"><h3>📅 Doanh thu theo tháº£ng</h3></div><div style="padding:16px"><canvas id="mc" height="160"></canvas></div></div>'
        '<div class="card"><div class="card-head"><h3>📦 Đơn hàng theo tháº£ng</h3></div><div style="padding:16px"><canvas id="oc" height="160"></canvas></div></div>'
        '</div>'
        '<div class="grid2">'
        '<div class="card"><div class="card-head"><h3>🥖 Doanh thu theo danh mục</h3></div><div style="padding:16px"><canvas id="cc" height="220"></canvas></div></div>'
        '<div class="card"><div class="card-head"><h3>📊 Chi tiết</h3></div>'
        '<table><thead><tr><th>Danh mục</th><th>Doanh thu</th></tr></thead><tbody>' + cat_rows + '</tbody></table></div>'
        '</div>'
        + script
    )
    return admin_layout(content, '📈 Báo Cáo', 'reports')


def page_admin_coupons():
    coupons = q("SELECT * FROM coupons ORDER BY id DESC")
    rows = ''
    for c in coupons:
        pct = int(c['used_count']/c['max_uses']*100) if c['max_uses'] else 0
        val = f"{int(c['discount_value'])}%" if c['discount_type']=='percent' else fmt(c['discount_value'])
        rows += f'<tr><td><code style="font-weight:800;color:#c2410c;font-size:13px">{e(c["code"])}</code></td><td style="color:#57534e">{("Phần trăm" if c["discount_type"]=="percent" else "Cố định")}</td><td style="font-weight:700">{val}</td><td>{fmt(c["min_order"])}</td><td><div style="display:flex;align-items:center;gap:6px"><div style="flex:1;height:6px;background:#e7e5e4;border-radius:3px;min-width:50px;overflow:hidden"><div style="height:100%;background:#c2410c;width:{pct}%;border-radius:3px"></div></div><span style="font-size:11px;color:#a8a29e">{c["used_count"]}/{c["max_uses"]}</span></div></td><td>{"<span class=s style=background:#dcfce7;color:#16a34a>Hoạt động</span>" if c["is_active"] else "<span class=s style=background:#fee2e2;color:#dc2626>Vô hiệu</span>"}</td></tr>'
    form = f"""<div style="background:#fff;border:1px solid #e7e5e4;border-radius:12px;padding:20px">
    <h3 style="font-size:13px;font-weight:700;margin-bottom:14px">➕ Tạo mã mới</h3>
    <form method="POST" action="/admin/coupons/add" style="display:flex;flex-direction:column;gap:10px">
      <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Mã *</label><input name="code" required placeholder="VD: SUMMER20" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-family:monospace;font-size:14px;font-weight:800;outline:none;text-transform:uppercase"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Loại</label><select name="discount_type" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"><option value="percent">Phần trăm (%)</option><option value="fixed">Số tiền cố định</option></select></div>
        <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Giá trị *</label><input name="discount_value" type="number" required placeholder="10" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Đơn tối thiểu</label><input name="min_order" type="number" value="0" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
        <div><label style="font-size:11px;font-weight:700;display:block;margin-bottom:4px">Số lượt tối đa</label><input name="max_uses" type="number" value="100" style="width:100%;padding:8px 11px;border:1px solid #e7e5e4;border-radius:7px;font-size:13px;outline:none"></div>
      </div>
      <button type="submit" class="btn btn-p" style="justify-content:center;padding:9px">Tạo mã giảm giá</button>
    </form></div>"""
    content = f'<div style="display:grid;grid-template-columns:1fr 360px;gap:16px;align-items:start"><div class="card"><div class="card-head"><h3>{len(coupons)} mã giảm giá</h3></div><table><thead><tr><th>Mã</th><th>Loại</th><th>Giá trị</th><th>Đơn tối thiểu</th><th>Đã dùng</th><th>Trạng thái</th></tr></thead><tbody>{rows}</tbody></table></div>{form}</div>'
    return admin_layout(content, '🎟️ Mã Giảm Giá', 'coupons')

# ─── REQUEST HANDLER ─────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default logging

    def get_sess(self):
        sid = get_session_id(dict(self.headers))
        if not sid:
            sid = str(uuid.uuid4())
        sess = get_session(sid)
        return sid, sess

    def send_html(self, html, code=200, extra_headers=None):
        body = html.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, url, sid=None, sess=None):
        if sid and sess is not None:
            save_session(sid, sess)
        self.send_response(302)
        if sid:
            self.send_header('Set-Cookie', f'sid={sid}; Path=/; HttpOnly; Max-Age=86400')
        self.send_header('Location', url)
        self.end_headers()

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length else b''

    def parse_form(self):
        body = self.read_body()
        pairs = body.decode('utf-8').split('&')
        d = {}
        for pair in pairs:
            if '=' in pair:
                k, v = pair.split('=', 1)
                d[unquote_plus(k)] = unquote_plus(v)
        return d

    def do_GET(self):
        sid, sess = self.get_sess()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)
        gp = lambda k, d='': qs.get(k, [d])[0]

        headers = {'Set-Cookie': f'sid={sid}; Path=/; HttpOnly; Max-Age=86400'}

        if path == '' or path == '/':
            return self.send_html(page_home(sess), extra_headers=headers)

        if path == '/menu':
            return self.send_html(page_menu(sort=gp('sort','popular'), search=gp('q'), sess=sess), extra_headers=headers)

        if path.startswith('/menu/'):
            slug = path[6:]
            return self.send_html(page_menu(slug=slug, sort=gp('sort','popular'), sess=sess), extra_headers=headers)

        if path.startswith('/product/'):
            slug = path[9:]
            result = page_product(slug, sess)
            if result is None:
                return self.send_html('<h1>404</h1>', 404)
            return self.send_html(result, extra_headers=headers)

        if path == '/checkout':
            result = page_checkout(sess)
            if result == 'redirect:/menu':
                return self.redirect('/menu', sid, sess)
            return self.send_html(result, extra_headers=headers)

        if path.startswith('/order/success/'):
            code = path[15:]
            result = page_order_success(code, sess)
            if not result: return self.send_html('<h1>404</h1>', 404)
            return self.send_html(result, extra_headers=headers)

        if path == '/order/track':
            return self.send_html(page_order_track(gp('code'), sess), extra_headers=headers)

        if path == '/login':
            return self.send_html(page_login(sess), extra_headers=headers)

        if path == '/register':
            return self.send_html(page_register(sess), extra_headers=headers)

        if path == '/logout':
            sess = {}
            return self.redirect('/', sid, sess)

        if path == '/account':
            result = page_account(sess)
            if result == 'redirect:/login': return self.redirect('/login', sid, sess)
            return self.send_html(result, extra_headers=headers)

        # Admin
        if path == '/admin':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_dashboard(), extra_headers=headers)

        if path == '/admin/orders':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_orders(gp('status')), extra_headers=headers)

        if path == '/admin/products':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_products(), extra_headers=headers)

        if path == '/admin/products/add':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_product_add(), extra_headers=headers)

        if path == '/admin/customers':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_customers(), extra_headers=headers)

        if path == '/admin/reports':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_reports(), extra_headers=headers)

        if path == '/admin/coupons':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            return self.send_html(page_admin_coupons(), extra_headers=headers)

        # API
        if path == '/api/search':
            q_str = gp('q')
            results = q("SELECT id,name,slug,image_emoji as emoji,price FROM products WHERE is_active=1 AND name LIKE ? LIMIT 8", (f'%{q_str}%',))
            return self.send_json([dict(r) for r in results])

        self.send_html('<h1>404 Not Found</h1>', 404)

    def do_POST(self):
        sid, sess = self.get_sess()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        headers_out = {'Set-Cookie': f'sid={sid}; Path=/; HttpOnly; Max-Age=86400'}
        ct = self.headers.get('Content-Type', '')

        if 'application/json' in ct:
            body = self.read_body()
            try: data = json.loads(body)
            except: data = {}
        else:
            data = {}

        # Cart add
        if path == '/api/cart/add':
            cart = sess.get('cart', {})
            pid = str(data.get('product_id'))
            qty = int(data.get('quantity', 1))
            prod = q("SELECT * FROM products WHERE id=?", (int(pid),), one=True)
            if prod:
                key = str(pid)
                if key in cart:
                    cart[key]['qty'] += qty
                else:
                    cart[key] = {'pid': prod['id'], 'name': prod['name'], 'price': prod['price'],
                                 'emoji': prod['image_emoji'], 'color': prod['image_color'], 'qty': qty}
                sess['cart'] = cart
                save_session(sid, sess)
                total = sum(v['price']*v['qty'] for v in cart.values())
                count = sum(v['qty'] for v in cart.values())
                return self.send_json({'success': True, 'total': total, 'count': count})
            return self.send_json({'success': False})

        # Cart update
        if path == '/api/cart/update':
            cart = sess.get('cart', {})
            key = str(data.get('key'))
            qty = int(data.get('quantity', 0))
            if key in cart:
                if qty <= 0: del cart[key]
                else: cart[key]['qty'] = qty
            sess['cart'] = cart
            save_session(sid, sess)
            total = sum(v['price']*v['qty'] for v in cart.values())
            count = sum(v['qty'] for v in cart.values())
            return self.send_json({'success': True, 'total': total, 'count': count})

        # Cart remove
        if path == '/api/cart/remove':
            cart = sess.get('cart', {})
            key = str(data.get('key'))
            cart.pop(key, None)
            sess['cart'] = cart
            save_session(sid, sess)
            total = sum(v['price']*v['qty'] for v in cart.values())
            count = sum(v['qty'] for v in cart.values())
            return self.send_json({'success': True, 'total': total, 'count': count})

        # Coupon apply
        if path == '/api/coupon/apply':
            code = data.get('code', '').upper()
            cart = sess.get('cart', {})
            total = sum(v['price']*v['qty'] for v in cart.values())
            coupon = q("SELECT * FROM coupons WHERE code=? AND is_active=1", (code,), one=True)
            if not coupon: return self.send_json({'success': False, 'message': 'Mã giảm giá không hợp lệ'})
            if coupon['used_count'] >= coupon['max_uses']: return self.send_json({'success': False, 'message': 'Mã đã hết lượt sử dụng'})
            if total < coupon['min_order']: return self.send_json({'success': False, 'message': f'Đơn tối thiểu {fmt(coupon["min_order"])}'})
            discount = total * coupon['discount_value'] / 100 if coupon['discount_type'] == 'percent' else coupon['discount_value']
            sess['coupon_code'] = code
            sess['coupon_discount'] = discount
            save_session(sid, sess)
            return self.send_json({'success': True, 'discount': discount, 'message': f'Áp dụng thành công! Giảm {fmt(discount)}'})

        # Review add
        if path == '/api/review/add':
            ex("INSERT INTO reviews(product_id,author_name,rating,content) VALUES(?,?,?,?)",
               (data.get('product_id'), data.get('name','Khách hàng'), int(data.get('rating',5)), data.get('content','')))
            ex("UPDATE products SET review_count=review_count+1 WHERE id=?", (data.get('product_id'),))
            return self.send_json({'success': True})

        # Checkout
        if path == '/checkout':
            form = self.parse_form()
            cart = sess.get('cart', {})
            if not cart:
                return self.redirect('/menu', sid, sess)
            discount = sess.get('coupon_discount', 0)
            coupon_code = sess.get('coupon_code', '')
            subtotal = sum(v['price']*v['qty'] for v in cart.values())
            total = subtotal + 30000 - discount
            code = 'BM' + datetime.now().strftime('%Y%m%d') + str(uuid.uuid4())[:4].upper()
            addr = f"{form.get('address','')}, {form.get('district','')}, {form.get('city','')}"
            user = sess.get('user')
            uid = user['id'] if user else None
            oid = ex("INSERT INTO orders(order_code,user_id,guest_name,guest_phone,guest_email,shipping_address,payment_method,subtotal,shipping_fee,discount,total,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, uid, form.get('name',''), form.get('phone',''), form.get('email',''), addr,
                 form.get('payment_method','cod'), subtotal, 30000, discount, total, form.get('note','')))
            for k, item in cart.items():
                ex("INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price,total_price) VALUES(?,?,?,?,?,?)",
                   (oid, item['pid'], item['name'], item['qty'], item['price'], item['price']*item['qty']))
                ex("UPDATE products SET sold_count=sold_count+? WHERE id=?", (item['qty'], item['pid']))
            if coupon_code:
                ex("UPDATE coupons SET used_count=used_count+1 WHERE code=?", (coupon_code,))
            sess['cart'] = {}
            sess.pop('coupon_code', None)
            sess.pop('coupon_discount', None)
            save_session(sid, sess)
            return self.redirect(f'/order/success/{code}', sid, sess)

        # Auth
        if path == '/login':
            form = self.parse_form()
            user = q("SELECT * FROM users WHERE email=?", (form.get('email',''),), one=True)
            if user and user['password_hash'] == hash_pw(form.get('password','')):
                sess['user'] = dict(user)
                save_session(sid, sess)
                return self.redirect('/admin' if user['role'] == 'admin' else '/', sid, sess)
            return self.send_html(page_login(sess, 'Email hoặc mật khẩu không đúng'), extra_headers=headers_out)

        if path == '/register':
            form = self.parse_form()
            existing = q("SELECT id FROM users WHERE email=?", (form.get('email',''),), one=True)
            if existing:
                return self.send_html(page_register(sess, 'Email đã được sử dụng'), extra_headers=headers_out)
            uid = ex("INSERT INTO users(name,email,phone,password_hash,role) VALUES(?,?,?,?,?)",
                (form.get('name',''), form.get('email',''), form.get('phone',''), hash_pw(form.get('password','')), 'customer'))
            user = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
            sess['user'] = dict(user)
            save_session(sid, sess)
            return self.redirect('/', sid, sess)

        # Admin actions
        if path.startswith('/admin/orders/') and path.endswith('/update'):
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            form = self.parse_form()
            parts = path.split('/')
            oid = int(parts[3])
            new_status = form.get('status','')
            if new_status in STATUS_LABELS:
                ex("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
                if new_status == 'completed':
                    ex("UPDATE orders SET payment_status='paid' WHERE id=?", (oid,))
            return self.redirect('/admin/orders', sid, sess)

        if path == '/admin/products/add':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            form = self.parse_form()
            ex("INSERT INTO products(name,slug,description,price,original_price,category_id,image_emoji,image_color,stock,is_featured) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (form.get('name',''), form.get('slug',''), form.get('description',''),
                float(form.get('price',0)), float(form.get('original_price',0)) or None,
                int(form.get('category_id',1)), form.get('image_emoji','🥖'),
                form.get('image_color','#f97316'), int(form.get('stock',100)),
                1 if 'is_featured' in form else 0))
            return self.redirect('/admin/products', sid, sess)

        if path == '/admin/coupons/add':
            if not sess.get('user') or sess['user'].get('role') != 'admin':
                return self.redirect('/login', sid, sess)
            form = self.parse_form()
            ex("INSERT OR IGNORE INTO coupons(code,discount_type,discount_value,min_order,max_uses) VALUES(?,?,?,?,?)",
               (form.get('code','').upper(), form.get('discount_type','percent'),
                float(form.get('discount_value',10)), float(form.get('min_order',0)),
                int(form.get('max_uses',100))))
            return self.redirect('/admin/coupons', sid, sess)

        self.send_html('<h1>404</h1>', 404)


if __name__ == '__main__':
    print("🥖 Khởi tạo cơ sở dữ liệu...")
    init_db()
    seed_db()
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"""
╔══════════════════════════════════════════════════╗
║        🥖  BÁNH MÌ BIN BIN - ONLINE              ║
╠══════════════════════════════════════════════════╣
║  🌐  Website:   http://localhost:{PORT}          ║
║  ⚙️   Admin:    http://localhost:{PORT}/admin    ║
║                                                  ║
║  👤  Admin login:                                ║
║      Email:    admin@binbin                      ║
║      Password: admin123                          ║
║                                                  ║
║  🎟️  Mã giảm giá demo:                           ║
║      WELCOME10 (giảm 10%)                        ║
║      FREESHIP  (miễn ship)                       ║
║      VIP50K    (giảm 50k)                        ║
╚══════════════════════════════════════════════════╝
""")
    server.serve_forever()
