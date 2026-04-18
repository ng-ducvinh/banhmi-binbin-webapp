# 🥖 Bánh Mì Huynh Hoa — Nền Tảng Bán Hàng Trực Tuyến

## Khởi Động Nhanh

```bash
python3 server.py
```

Truy cập: http://localhost:5000  
Trang admin: http://localhost:5000/admin  
Tài khoản admin: `admin@banhmihuynhhoa.vn` / `admin123`

---

## Tính Năng

### 🛍️ Khách Hàng
- Trang chủ động với sản phẩm nổi bật, bán chạy
- Danh mục sản phẩm (lọc, sắp xếp)
- Trang chi tiết sản phẩm với đánh giá & sản phẩm liên quan
- Giỏ hàng trượt (sidebar) với cập nhật real-time
- Thanh toán nhiều bước (COD / Chuyển khoản / MoMo / VNPay)
- Mã giảm giá (% hoặc cố định)
- Tra cứu đơn hàng theo mã
- Đăng ký / Đăng nhập tài khoản
- Trang quản lý đơn hàng cá nhân
- Tìm kiếm sản phẩm realtime

### ⚙️ Quản Trị (Admin)
- Dashboard tổng quan (doanh thu, đơn hàng, KPIs)
- Biểu đồ doanh thu 7 ngày (Chart.js)
- Quản lý đơn hàng (lọc theo trạng thái, cập nhật 4 bước)
- Quản lý sản phẩm (thêm, xem)
- Quản lý khách hàng
- Báo cáo doanh thu (theo tháng, theo danh mục)
- Quản lý mã giảm giá

---

## Luồng Đơn Hàng (4 Bước)
```
Chờ xác nhận → Đã xác nhận → Đang giao → Hoàn thành
```

## Mã Giảm Giá Demo
| Mã | Loại | Giá trị | Đơn tối thiểu |
|----|------|---------|---------------|
| WELCOME10 | % | 10% | 100.000đ |
| FREESHIP | Cố định | 30.000đ | 80.000đ |
| VIP50K | Cố định | 50.000đ | 200.000đ |

---

## Kiến Trúc Kỹ Thuật

```
server.py              ← HTTP server (Python stdlib)
├── SQLite3            ← Cơ sở dữ liệu (banhmi.db)
├── Sessions           ← Cookie-based session (bảng sessions)
├── Cart               ← Giỏ hàng lưu trong session
└── Pages
    ├── Customer        ← Trang khách hàng
    └── Admin           ← Trang quản trị
```

**Không cần pip install gì cả** — chỉ cần Python 3.8+

---

## Cấu Trúc Dữ Liệu

| Bảng | Mô tả |
|------|-------|
| `users` | Tài khoản (customer + admin) |
| `categories` | Danh mục sản phẩm |
| `products` | Sản phẩm với giá, tồn kho, emoji |
| `orders` | Đơn hàng với trạng thái 4 bước |
| `order_items` | Chi tiết từng sản phẩm trong đơn |
| `reviews` | Đánh giá sản phẩm |
| `coupons` | Mã giảm giá |
| `sessions` | Phiên đăng nhập |

---

## API Endpoints

| Method | Đường dẫn | Mô tả |
|--------|-----------|-------|
| POST | `/api/cart/add` | Thêm vào giỏ |
| POST | `/api/cart/update` | Cập nhật số lượng |
| POST | `/api/cart/remove` | Xóa khỏi giỏ |
| POST | `/api/coupon/apply` | Áp dụng mã giảm giá |
| POST | `/api/review/add` | Thêm đánh giá |
| GET  | `/api/search?q=` | Tìm kiếm sản phẩm |

---

## Bảo Mật
- Mật khẩu mã hóa SHA-256 + salt
- Session token ngẫu nhiên UUID4
- Phân quyền admin vs customer
- HTML escape đầu vào (XSS prevention)
- HttpOnly cookie

