import cv2
import numpy as np
import requests
import os
import time

def analyze_plant_growth(image_source):
    """
    이미지 소스(URL 또는 로컬 파일 경로)를 받아 식물의 초록색 영역 비율을 분석합니다.
    """
    try:
        # 1. 이미지 로드
        if image_source.startswith('http'):
            # URL 이미지 다운로드
            try:
                resp = requests.get(image_source, stream=True, timeout=5)
                if resp.status_code == 200:
                    image_array = np.asarray(bytearray(resp.content), dtype="uint8")
                    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                else:
                    return {"error": f"Failed to download image (Status: {resp.status_code})"}
            except Exception as e:
                return {"error": f"Download Error: {str(e)}"}
        else:
            # 로컬 파일
            if os.path.exists(image_source):
                image = cv2.imread(image_source)
            else:
                return {"error": "Local file not found"}

        if image is None:
            return {"error": "Failed to decode image"}

        # 2. 이미지 전처리 (HSV 변환)
        # BGR -> HSV (Hue, Saturation, Value)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # 3. 초록색 마스크 생성 (식물 영역 추출)
        # Hue 범위: 35(연두) ~ 85(진초록)
        # Saturation: 40 ~ 255 (너무 흐릿한 색 제외)
        # Value: 40 ~ 255 (너무 어두운 색 제외)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # 노이즈 제거 (Morphology)
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # 4. 면적 계산
        height, width = image.shape[:2]
        total_pixels = height * width
        green_pixels = cv2.countNonZero(mask)
        growth_ratio = (green_pixels / total_pixels) * 100
        
        # 5. 결과 시각화 (원본 + 마스크 합성)
        # 초록색 영역만 원본 색상 유지, 나머지는 흑백 처리
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        
        # 마스크 영역은 원본, 아닌 영역은 흑백
        result_img = np.where(mask[:, :, None] == 255, image, gray_bgr)
        
        # 텍스트 추가
        cv2.putText(result_img, f"Growth: {growth_ratio:.2f}%", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 결과 이미지 저장 (html 폴더 내에 저장하여 웹에서 접근 가능하게 함)
        save_name = f"analysis_result.jpg"
        save_path = os.path.join("html", save_name)
        cv2.imwrite(save_path, result_img)
        
        return {
            "success": True,
            "green_pixels": green_pixels,
            "total_pixels": total_pixels,
            "ratio": round(growth_ratio, 2),
            "image_url": save_name,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Test Code
    test_url = "https://images.unsplash.com/photo-1530836369250-ef72a3f5cda8?q=80&w=800&auto=format&fit=crop"
    print("Testing analysis with sample image...")
    result = analyze_plant_growth(test_url)
    print(result)
