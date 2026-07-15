import subprocess
import sys
import time
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def log(message):
    print(f"🌟 [마스터 스타터] {message}")

def main():
    processes = []
    try:
        log("전체 비동기 DB 큐 파이프라인 시스템 구동 시작...")
        
        # 1. API 서버 구동 (포트 8000)
        log("1. API 서버 (api_server.py) 구동 중...")
        api_path = os.path.join(CURRENT_DIR, "api_server.py")
        processes.append(subprocess.Popen([sys.executable, api_path]))
        time.sleep(2)
        
        # 2. 쿠팡 크롤링 워커 구동
        log("2. 쿠팡 크롤링 워커 (worker_coupang_crawler.py) 구동 중...")
        crawler_path = os.path.join(CURRENT_DIR, "worker_coupang_crawler.py")
        processes.append(subprocess.Popen([sys.executable, crawler_path]))
        time.sleep(1)
        
        # 3. LLM 매칭 워커 구동
        log("3. LLM 매칭 워커 (worker_llm_matcher.py) 구동 중...")
        matcher_path = os.path.join(CURRENT_DIR, "worker_llm_matcher.py")
        processes.append(subprocess.Popen([sys.executable, matcher_path]))
        
        log("==================================================================")
        log("✅ 모든 프로세스가 백그라운드에서 구동되었습니다.")
        log("👉 API 서버 포트: http://localhost:8000")
        log("👉 작업 상태 확인 API: http://localhost:8000/api/pipeline/status")
        log("👉 전체 상품 리스트 API: http://localhost:8000/api/products")
        log("👉 수집 강제 트리거 API: POST http://localhost:8000/api/products/trigger")
        log("⚠️ (종료하려면 터미널에서 Ctrl+C를 누르세요)")
        log("==================================================================")
        
        # 모든 자식 프로세스가 종료될 때까지 대기
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        log("\n🛑 시스템 종료 요청 감지. 모든 백그라운드 프로세스를 강제 종료합니다...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        log("✨ 모든 프로세스가 정상 종료되었습니다.")

if __name__ == "__main__":
    main()
