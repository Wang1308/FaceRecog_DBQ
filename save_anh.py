import os
import psycopg2
import shutil  # Dùng để xóa toàn bộ thư mục

# Kết nối đến PostgreSQL
def connect_db():
    try:
        conn = psycopg2.connect(
            dbname="face_attendance",
            user="postgres",
            password="quang",
            host="localhost",  # Nếu chạy trên máy local
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"Error: {e}")
        return None

# Hàm xóa tất cả dữ liệu trong thư mục
def clear_processed_folder():
    processed_folder = 'Dataset/Facedata/processed'
    if os.path.exists(processed_folder):
        shutil.rmtree(processed_folder)  # Xóa toàn bộ thư mục processed
    os.makedirs(processed_folder)  # Tạo lại thư mục rỗng

# Lưu ảnh vào thư mục riêng của nhân viên
def save_images_to_folder(employee_id, name, images):
    base_folder = 'Dataset/Facedata/raw'
    # Tạo thư mục cho nhân viên nếu chưa có
    employee_folder = os.path.join(base_folder, name)
    if not os.path.exists(employee_folder):
        os.makedirs(employee_folder)
    
    # Lưu ảnh vào thư mục của nhân viên
    for i, img in enumerate(images, 1):
        file_path = os.path.join(employee_folder, f"{name}_{i}.jpg")
        with open(file_path, 'wb') as f:
            f.write(img)

    # Sau khi lưu xong, xóa dữ liệu trong thư mục processed
    clear_processed_folder()

# Lấy ảnh từ cơ sở dữ liệu và lưu vào thư mục của mỗi nhân viên
def fetch_and_save_images():
    conn = connect_db()
    if conn is None:
        return
    
    cur = conn.cursor()
    cur.execute("SELECT id, name, face_image1, face_image2, face_image3, face_image4, face_image5 FROM employees")
    employees = cur.fetchall()
    
    for emp in employees:
        emp_id, name, *images = emp
        save_images_to_folder(emp_id, name, images)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    fetch_and_save_images()
