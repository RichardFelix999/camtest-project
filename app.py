import sys
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog)
import boto3
from datetime import datetime
import os

from dotenv import load_dotenv

load_dotenv()
# Set the values of your computer vision endpoint and computer vision key
# as environment variables:
try:
    aws_access_key_id = os.getenv("access_ID")
    aws_secret_access_key = os.getenv("access_Key")
    
    print("Debug - Access Key ID:", aws_access_key_id)
    print("Debug - Secret Key length:", len(aws_secret_access_key) if aws_secret_access_key else 0)
    
except KeyError:
    print("Missing environment variable 'access_ID' or 'access_Key'")
    print("Set them before running this sample.")
    exit()

class ImageUploaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Uploader")
        self.setGeometry(100, 100, 800, 600)
        self.setFixedSize(800,600)
        
        # Initialize variables
        self.camera = None
        self.current_image = None
        self.captured_image = None
        self.camera_resolution = (1920, 1080)  # Full HD resolution
        
        # Create UI
        self.init_ui()
        self.check_camera()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Layouts
        main_layout = QVBoxLayout()
        button_layout = QHBoxLayout()
        
        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #cccccc;
                border-radius: 10px;
            }
        """)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, 
                                      QtWidgets.QSizePolicy.Expanding)
        
        # Buttons
        # self.capture_btn = QPushButton("Capture")
        self.send_btn = QPushButton("Send")
        self.upload_btn = QPushButton("Upload Image")
        self.clear_btn = QPushButton("Clear")
        
        # Button styling
        button_style = """
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                border-radius: 5px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        for btn in [self.send_btn, self.upload_btn, self.clear_btn]:
            btn.setStyleSheet(button_style)
                
        # Layout organization
        # button_layout.addWidget(self.capture_btn)
        button_layout.addWidget(self.send_btn)
        button_layout.addWidget(self.upload_btn)
        button_layout.addWidget(self.clear_btn)
        
        main_layout.addWidget(self.image_label, 1)
        main_layout.addLayout(button_layout)
        main_widget.setLayout(main_layout)
        
        # Connect signals
        # self.capture_btn.clicked.connect(self.capture_image)
        self.send_btn.clicked.connect(self.send_to_cdn)
        self.upload_btn.clicked.connect(self.upload_image)
        self.clear_btn.clicked.connect(self.clear_display)
        
        # Setup camera timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
    def check_camera(self):
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.show_camera_placeholder()
            return
            
        # Try to set camera resolution to Full HD
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_resolution[0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_resolution[1])
        
        # Get actual resolution (might be different from requested)
        actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"Camera resolution: {actual_width}x{actual_height}")
        
        self.timer.start(30)  # 30ms update interval
    
    def show_camera_placeholder(self):
        self.image_label.setText("Camera Not Found")
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                color: #666666;
                font-size: 24px;
                border: 2px dashed #cccccc;
                border-radius: 10px;
            }
        """)
    
    def update_frame(self):
        ret, frame = self.camera.read()
        if ret:
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = image.shape
            bytes_per_line = ch * w
            qt_image = QtGui.QImage(image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qt_image)
            self.current_image = pixmap
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        
    def upload_image(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", 
            "Images (*.png *.jpg *.jpeg)", options=options)
        
        if file_name:
            self.captured_image = QtGui.QPixmap(file_name)
            self.image_label.setPixmap(self.captured_image.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if self.camera and self.camera.isOpened():
                self.timer.stop()
                self.camera.release()
    
    def send_to_cdn(self):
        # If camera is active, capture the current frame first
        if self.camera and self.camera.isOpened() and self.current_image:
            self.captured_image = self.current_image
            self.image_label.setPixmap(self.captured_image.scaled(
                self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.timer.stop()
            self.camera.release()

        if self.captured_image:
            try:
                # Save to a temporary file with high quality
                temp_file = "temp_upload.jpg"
                # Use PNG for maximum quality if needed
                if self.camera and self.camera.isOpened():
                    self.captured_image.save(temp_file, "PNG")  # Lossless format for camera captures
                else:
                    self.captured_image.save(temp_file, "JPEG", quality=95)  # High quality JPEG for uploaded images
                
                # Initialize S3 client using environment variables or config file
                cdn_handler = boto3.client('s3',
                    endpoint_url='https://nyc3.digitaloceanspaces.com',
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
                
                # Generate a unique filename using timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                cdn_filename = f'test/image_{timestamp}.jpg'
                
                # Upload the file
                cdn_handler.upload_file(
                    temp_file, 
                    'divinetradingcardllccdn', 
                    cdn_filename,
                    ExtraArgs={'ACL': 'public-read'}
                )
                
                print(f"Image uploaded successfully as {cdn_filename}")
                
                return f'https://divinetradingcardllccdn.nyc3.digitaloceanspaces.com/{cdn_filename}'
            except Exception as e:
                print(f"Error uploading to CDN: {str(e)}")
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        else:
            print("No image to upload. Please camera on or upload an image first.")
    
    def clear_display(self):
        self.captured_image = None
        self.image_label.clear()
        self.check_camera()  # Restart camera if available
    
    def closeEvent(self, event):
        if self.camera and self.camera.isOpened():
            self.camera.release()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageUploaderApp()
    window.show()
    sys.exit(app.exec_())