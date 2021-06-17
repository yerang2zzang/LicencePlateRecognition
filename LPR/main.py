import cv2

try:
	from PIL import Image
except ImportError:
	import Image
import pytesseract
from skimage.filters import (threshold_otsu, threshold_niblack, threshold_sauvola)
import numpy as np

import sys, os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QCoreApplication, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QPixmap, QIcon, QImage
import time

class ImageLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.initImageLabel()

    def initImageLabel(self):
        self.setFixedHeight(370)
        self.setText('\n\n Drop Image Here \n\n')
        self.setStyleSheet('''
                    QLabel{
                    border : 2px dashed #aaa
                    }
                ''')

    def setPixmap(self, image):
        image = image.scaledToHeight(370)
        super().setPixmap(image)

class Table(QTableWidget):
    def __init__(self, row, col):
        super().__init__()
        self.clear()
        self.limitRow=row
        self.limitCol=col
        self.nowRow=0
        self.initTable()

    def initTable(self):
        self.setFixedHeight(170)
        self.setRowCount(self.limitRow)
        self.setColumnCount(self.limitCol)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setTableWidgetData()
        self.resizeColumnsToContents()

    def setTableWidgetData(self):
        column_headers = ['파일명', '번호판', '번호판 영역(좌상단, 우하단)', '파일 위치']
        self.setHorizontalHeaderLabels(column_headers)

    def set_data(self, cnt, recoInfo):
        self.setItem(cnt, 0, QTableWidgetItem(recoInfo['filename']))
        self.setItem(cnt, 1, QTableWidgetItem(recoInfo['text']))
        self.setItem(cnt, 2, QTableWidgetItem("({0}, {1}), ({2}, {3})".format(recoInfo['axis'][0][0], recoInfo['axis'][0][1], recoInfo['axis'][3][0],recoInfo['axis'][3][1])))
        self.setItem(cnt, 3, QTableWidgetItem(recoInfo['filepath']))


class AppDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.cnt=-1
        self.nowRow=self.nowCol=0
        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 600, 600)
        self.setFixedSize(600, 600)
        self.setAcceptDrops(True)

        # 위젯 선언
        self.photoViewer = ImageLabel()
        self.quitButton = QPushButton('종료')
        self.clearButton = QPushButton('초기화')
        self.tableViewer = Table(20,4)
        self.showContourBoxButton = QPushButton('영역 감지 결과 보기')
        self.showPlateButton = QPushButton('번호판 이미지 보기')

        # 버튼 기능 연동
        self.quitButton.clicked.connect(QCoreApplication.instance().quit)
        self.clearButton.clicked.connect(self.clearBtn)
        self.showContourBoxButton.clicked.connect(self.contourBtn)
        self.showPlateButton.clicked.connect(self.plateBtn)

        # Table Event
        self.tableViewer.cellDoubleClicked.connect(self.selectCell)

        # Add Widget on Grid Layout
        photoHeight=6
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.photoViewer, 0, 0, photoHeight-3, 4)
        mainLayout.addWidget(self.tableViewer, photoHeight-3, 0, 2, 4)
        mainLayout.addWidget(self.showContourBoxButton, 5, 0)
        mainLayout.addWidget(self.showPlateButton, 5, 1)
        mainLayout.addWidget(self.clearButton, 5, 2)
        mainLayout.addWidget(self.quitButton, 5, 3)


        # Window Setting
        self.setWindowTitle('자동차 번호판 인식 프로그램')
        self.setWindowIcon(QIcon('car_icon.ico'))
        self.setLayout(mainLayout)

    def clearBtn(self):
        self.cnt = -1
        self.nowRow = self.nowCol = 0
        self.tableViewer.clear()
        self.tableViewer.setTableWidgetData()
        self.photoViewer.clear()
        self.photoViewer.initImageLabel()

    def contourBtn(self):
        if self.tableViewer.item(self.nowRow, self.nowCol):
            cv2.destroyAllWindows()
            img = cv2.imread('images/contourBox(%i).jpg' % self.nowRow)
            dst=cv2.resize(img, dsize=(0,0),fx=0.5,fy=0.5,interpolation=cv2.INTER_LINEAR)
            cv2.imshow("Licence Plate Detection Result", dst)
            cv2.waitKey(0)


    def plateBtn(self):
        if self.tableViewer.item(self.nowRow, self.nowCol):
            cv2.destroyAllWindows()
            img=cv2.imread('images/lastImage(%i).jpg' % self.nowRow)
            cv2.imshow("NumPlate", img)
            cv2.waitKey(0)



    def dragEnterEvent(self, event):
        if  event.mimeData().hasImage:
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if  event.mimeData().hasImage:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasImage:
            self.cnt=self.cnt+1
            self.nowRow+=1
            self.nowCol+=1
            event.setDropAction(Qt.CopyAction)
            file_path = event.mimeData().urls()[0].toLocalFile()
            self.set_image(file_path)
            cv_image=cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            imp=ImageProcessing(cv_image, self.cnt)
            fileText=file_path.split('/')
            # print(fileText[-1])
            recoInfo = {'axis':imp.axis,'text':imp.text, 'filename':fileText[-1], 'filepath':file_path}
            self.tableViewer.set_data(self.cnt, recoInfo)
            event.accept()
        else:
            event.ignore()

    def set_image(self, file_path):
        self.photoViewer.setPixmap(QPixmap(file_path))

    def selectCell(self, row, column):
        if self.tableViewer.item(row,column):
            self.nowRow=row
            self.nowCol=column
            self.tableViewer.nowRow=row
            self.photoViewer.setPixmap(QPixmap(self.tableViewer.item(row, 3).text()))


class ImageProcessing(AppDemo):
	def __init__(self, image, cnt):
		self.image = image
		self.cnt = cnt
		self.start = time.time()
		self.beforeProcessing(False)
		self.startProcessing()

	def startProcessing(self):
		# 변수 선언
		self.contours_dict = []
		self.pos_cnt = list()

		self.findContour()
		self.pickContour()
		self.perspectiveTransform()
		self.addBorder()
		self.beforeProcessing(True)

		self.textReco()


	def beforeProcessing(self, is2nd):
		if(is2nd==True):
			img=self.border
		else :
			img=self.image

		self.imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
		self.rgbGray = cv2.cvtColor(self.imgRGB, cv2.COLOR_RGB2GRAY)

		if is2nd == False:
			img_blurred = cv2.bilateralFilter(self.rgbGray, -1, 10, 5)
		if is2nd == True:
			img_blurred = cv2.medianBlur(self.rgbGray, 7)

		cv2.imwrite('images/blurredNumPlate(%i).jpg' % self.cnt, img_blurred)

		thresh_sauvola = threshold_sauvola(img_blurred, 25)
		binary_sauvola = img_blurred > thresh_sauvola
		binary_sauvola = (binary_sauvola).astype('uint8')
		binary_sauvola = binary_sauvola * 255
		self.th = binary_sauvola
		self.th = (self.th).astype('uint8')

		cv2.imwrite('images/secondNumPlate(%i).jpg' % self.cnt, self.th)

	def findContour(self):
		contours, _ = cv2.findContours(self.th, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
		orig_img = self.image.copy()

		for contour in contours:
			x, y, w, h = cv2.boundingRect(contour)
			cv2.rectangle(orig_img, pt1=(x, y), pt2=(x + w, y + h), color=(0, 255, 0), thickness=1)

			self.contours_dict.append({
				'contour': contour,
				'x': x,
				'y': y,
				'w': w,
				'h': h,
				'cx': x + (w / 2),
				'cy': y + (h / 2)
			})

	def pickContour(self):
		## 컨투어 추리기 1st
		count = 0
		for d in self.contours_dict:
			rect_area = d['w'] * d['h']
			aspect_ratio = d['w'] / d['h']

			if (aspect_ratio >= 0.3) and (aspect_ratio <= 1.0) and (rect_area >= 800) and (rect_area <= 2000):
				d['idx'] = count
				count += 1
				self.pos_cnt.append(d)

		## 컨투어 추리기 2nd
		self.result_idx = self.find_number(self.pos_cnt)
		matched_result = []
		for idx_list in self.result_idx:
			matched_result.append(np.take(self.pos_cnt, idx_list))
		return matched_result

	def find_number(self, contour_list):
		MAX_DIAG_MULTIPLYER = 7  # contourArea의 대각선 x7 안에 다음 contour가 있어야함
		MAX_ANGLE_DIFF = 15.0  # contour와 contour 중심을 기준으로 한 각도가 설정각 이내여야함 --> 카메라 각도가 너무 틀어져있으면 이 각도로 측정되지 않을 수 있음에 주의...
		MAX_AREA_DIFF = 0.5  # contour간에 면적 차이가 설정값보다 크면 인정하지 x
		MAX_WIDTH_DIFF = 0.8  # contour간에 너비 차이가 설정값보다 크면 인정 x
		MAX_HEIGHT_DIFF = 0.2  # contour간에 높이 차이가 크면 인정 x
		MIN_N_MATCHED = 3  # 위의 조건을 따르는 contour가 최소 3개 이상이어야 번호판으로 인정
		MAX_N_MATCHED = 8

		if (len(contour_list) < 3):
			return

		matched_result_idx = []

		# contour_list[n]의 keys = dict_keys(['contour', 'x', 'y', 'w', 'h', 'cx', 'cy', 'idx'])
		for d1 in contour_list:
			matched_contour_idx = []
			for d2 in contour_list:  # for문을 2번 돌면서 d1과 d2를 비교할 것임
				if d1['idx'] == d2['idx']:
					continue

				# 피타고라스로 대각 길이를 구하기 위해 dy와 dx를 구함.
				dx = abs(d1['cx'] - d2['cx'])  # 각각 중앙점 기준으로 가로 거리
				dy = abs(d1['cy'] - d2['cy'])  # 각각 중앙점 기준으로 세로 거리

				# d1 사각형의 대각선 거리
				diag_len = np.sqrt(d1['w'] ** 2 + d1['w'] ** 2)

				# contour 중심간의 거리 (L2 norm으로 계산한 거리)
				distance = np.linalg.norm(np.array([d1['cx'], d1['cy']]) - np.array([d2['cx'], d2['cy']]))

				# 각도 구하기
				# tan세타 = dy / dx
				# 세타 = arctan(dy/dx) (using 역함수)
				if dx == 0:
					angle_diff = 90  # x축의 차이가 없다는 것은 contour가 서로 위/아래에 위치한다는 것
				else:
					angle_diff = np.degrees(np.arctan(dy / dx))  # 라디안 값을 도로 바꾼다.

				# 면적/너비/높이의 비율 (기준 contour 대비)
				area_diff = abs(d1['w'] * d1['h'] - d2['w'] * d2['h']) / (d1['w'] * d1['h'])
				width_diff = abs(d1['w'] - d2['w']) / d1['w']
				height_diff = abs(d1['h'] - d2['h']) / d2['h']

				# 조건에 맞는 idx만을 matched_contours_idx에 append할 것이다.
				if distance < diag_len * MAX_DIAG_MULTIPLYER and angle_diff < MAX_ANGLE_DIFF \
						and area_diff < MAX_AREA_DIFF and width_diff < MAX_WIDTH_DIFF \
						and height_diff < MAX_HEIGHT_DIFF:
					matched_contour_idx.append(d2['idx'])
			matched_contour_idx.append(d1['idx'])

			# 앞서 정한 후보군의 갯수보다 적으면 탈락
			if len(matched_contour_idx) < MIN_N_MATCHED:
				continue
			elif len(matched_contour_idx) >= MAX_N_MATCHED:
				continue

			# 최종 contour 묶음을 입력
			matched_result_idx.append(matched_contour_idx)

			# 최종 묶음에 들지 못한 애들은 따로 구분.
			unmatched_contour_idx = []
			for d4 in contour_list:
				if d4['idx'] not in matched_contour_idx:
					unmatched_contour_idx.append(d4['idx'])

			# 묶음이 안된 애 전체 정보를 unmatched_contour에 대입.
			unmatched_contour = np.take(self.pos_cnt, unmatched_contour_idx)

			# 묶음 안된 애들에 대해 재귀로 돈다.
			recursive_contour_list = self.find_number(unmatched_contour)

			# 최종 리스트에 추가
			for idx in recursive_contour_list:
				matched_result_idx.append(idx)
			break
		return matched_result_idx

	def perspectiveTransform(self):
		# 원근 변환
		matched_result = []
		for idx_list in self.result_idx:
			matched_result.append(np.take(self.pos_cnt, idx_list))

		for i, matched_chars in enumerate(matched_result):
			orig_img = self.image.copy()
			# lambda 함수로 소팅. 'cx'의 키값을 오름차순으로 정렬한다.
			sorted_chars = sorted(matched_chars, key=lambda x: x['cx'])

			# 0번째 중앙 x좌표에서 마지막 중앙 x좌표까지의 길이
			plate_cx = (sorted_chars[0]['cx'] + sorted_chars[-1]['cx']) / 2
			plate_cy = (sorted_chars[0]['cy'] + sorted_chars[-1]['cy']) / 2

			# 번호판 영역의 네 모서리 좌표를 저장한다.
			leftUp = {'x': sorted_chars[0]['x'], 'y': sorted_chars[0]['y']}
			leftDown = {'x': sorted_chars[0]['x'], 'y': sorted_chars[0]['y'] + sorted_chars[0]['h']}
			rightUp = {'x': sorted_chars[-1]['x'] + sorted_chars[-1]['w'], 'y': sorted_chars[-1]['y']}
			rightDown = {'x': sorted_chars[-1]['x'] + sorted_chars[-1]['w'],
						 'y': sorted_chars[-1]['y'] + sorted_chars[-1]['h']}

			# 원근 변환을 위해 input 좌표와 output 좌표를 기록 (좌상->좌하->우상->우하) (번호판 크기에 따라서 pts2는 달라질 수 있음에 주의)
			pts1 = np.float32([[leftUp['x'], leftUp['y']], [leftDown['x'], leftDown['y']], [rightUp['x'], rightUp['y']],
							   [rightDown['x'], rightDown['y']]])
			pts2 = np.float32([[0, 0], [0, 110], [520, 0], [520, 110]])
			self.axis=pts1

			# 다각형 선을 그리기 위해서 (좌상->좌하->우하->우상)
			ptsPoly = np.array(
				[[leftUp['x'], leftUp['y']], [leftDown['x'], leftDown['y']], [rightDown['x'], rightDown['y']],
				 [rightUp['x'], rightUp['y']]])

			M = cv2.getPerspectiveTransform(pts1, pts2)
			dst = cv2.warpPerspective(self.th, M, (520, 110))
			self.numPlate = dst.copy()

			# 점과 선 그리기
			orig_img = cv2.polylines(orig_img, [ptsPoly], True, (0, 255, 255), 2)
			cv2.circle(orig_img, (leftUp['x'], leftUp['y']), 10, (255, 0, 0), -1)
			cv2.circle(orig_img, (leftDown['x'], leftDown['y']), 10, (0, 255, 0), -1)
			cv2.circle(orig_img, (rightUp['x'], rightUp['y']), 10, (0, 0, 255), -1)
			cv2.circle(orig_img, (rightDown['x'], rightDown['y']), 10, (0, 0, 0), -1)

			cv2.imwrite('images/numPlate(%i).jpg' % self.cnt, self.numPlate)
			cv2.imwrite('images/contourBox(%i).jpg' % self.cnt, orig_img)

	def addBorder(self):
		bordersize = 100

		self.border = cv2.copyMakeBorder(
			self.numPlate,
			top=bordersize,
			bottom=bordersize,
			left=bordersize,
			right=bordersize,
			borderType=cv2.BORDER_CONSTANT,
			value=[255, 255, 255]
		)
		cv2.imwrite('images/Border(%i).jpg' % self.cnt, self.border)

	def textReco(self):
		self.text = pytesseract.image_to_string(self.th, lang='kor', config='--psm 7')
		cv2.imwrite('images/lastImage(%i).jpg' % self.cnt, self.th)
		self.text = self.text.split('\x0c')[0]
		self.text = self.text.split('\n')[0]
		print('text = ',self.text)
		if not self.text :
			self.text='인식 실패'
		print("처리 경과 시간 :", time.time() - self.start)
		print('-----------------------------------------')




if __name__ == '__main__':
	app = QApplication(sys.argv)
	demo = AppDemo()
	demo.show()
	sys.exit(app.exec_())