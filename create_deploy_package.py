import zipfile
import os
import datetime

def create_deploy_package():
    # 현재 날짜로 파일명 생성
    timestamp = datetime.datetime.now().strftime("%Y%m%d")
    zip_filename = f"MQnetFarm_Deploy_{timestamp}.zip"
    
    # 제외할 디렉토리 및 파일
    exclude_dirs = {'__pycache__', '.git', '.vscode', '.idea', 'venv', 'env'}
    exclude_files = {zip_filename, os.path.basename(__file__), '.DS_Store', 'Thumbs.db'}
    exclude_exts = {'.pyc', '.tmp', '.log'}

    cwd = os.getcwd()
    print(f"📦 패키징 시작: {cwd} -> {zip_filename}")

    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(cwd):
                # 제외할 디렉토리 필터링
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file in exclude_files:
                        continue
                    
                    _, ext = os.path.splitext(file)
                    if ext.lower() in exclude_exts:
                        continue

                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=cwd)
                    
                    try:
                        zipf.write(file_path, arcname)
                        print(f"  + 추가: {arcname}")
                    except PermissionError:
                        print(f"  ⚠️ 건너뜀 (권한 부족/사용 중): {arcname}")
                    except Exception as e:
                        print(f"  ⚠️ 에러 ({file}): {e}")

        print("\n✅ 배포 파일 생성 완료!")
        print(f"📁 파일명: {zip_filename}")
        print(f"📏 크기: {os.path.getsize(zip_filename) / 1024:.2f} KB")

    except Exception as e:
        print(f"\n❌ 패키징 실패: {e}")

if __name__ == "__main__":
    create_deploy_package()
