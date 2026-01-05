import pygame
import random
import sys
import asyncio
import io
import csv

# -------------------- 설정 --------------------
# ★ 여기에 구글 시트에서 "웹에 게시 -> CSV"로 얻은 URL을 넣으세요!
# (테스트용으로 제가 만든 시트 주소를 넣어뒀습니다. PETER님 걸로 바꾸시면 됩니다.)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSjim8tnfOemk_eCrfikI5jl105bSbpv2uMP0ZZNPZJOHbKZIY2j_tvhIo3xIi7LVqSHz1gYTEHt6f1/pub?gid=0&single=true&output=csv"

# 화면 설정 (세로 1440 모니터 대응)
SCREEN_WIDTH = 540
SCREEN_HEIGHT = 900  
FPS = 60
INITIAL_LIVES = 3

# -------------------- 웹/로컬 환경 구분 및 데이터 로드 --------------------
IS_WEB = sys.platform == "emscripten"

async def fetch_csv_data(url):
    """인터넷(구글시트)에서 CSV 데이터를 가져와 파싱하는 함수"""
    print("데이터 다운로드 중...")
    csv_text = ""
    
    if IS_WEB:
        # 웹 브라우저 환경 (pyodide)
        from pyodide.http import pyfetch
        try:
            response = await pyfetch(url)
            if response.status == 200:
                csv_text = await response.string()
            else:
                print(f"다운로드 실패: {response.status}")
        except Exception as e:
            print(f"웹 데이터 로드 에러: {e}")
    else:
        # 로컬 PC 환경 (requests 라이브러리 필요)
        try:
            import requests
            response = requests.get(url)
            if response.status_code == 200:
                csv_text = response.text
        except ImportError:
            print("로컬 테스트 시 'pip install requests'가 필요합니다.")
        except Exception as e:
            print(f"로컬 데이터 로드 에러: {e}")

    # CSV 파싱 (level, word, meaning)
    parsed_data = []
    if csv_text:
        try:
            f = io.StringIO(csv_text)
            reader = csv.DictReader(f)
            for row in reader:
                # 구글 시트 헤더가 level, word, meaning 이라고 가정
                if row['level'] and row['word']:
                    parsed_data.append({
                        "level": int(row['level']),
                        "word": row['word'].strip(),
                        "meaning": row['meaning'].strip()
                    })
            print(f"총 {len(parsed_data)}개의 단어를 로드했습니다.")
        except Exception as e:
            print(f"CSV 파싱 에러: {e}")
    
    return parsed_data

# -------------------- 음성 (TTS) --------------------
def speak_word(text):
    if IS_WEB:
        try:
            from platform import window
            utterance = window.SpeechSynthesisUtterance.new(text)
            utterance.lang = "en-US"
            window.speechSynthesis.speak(utterance)
        except: pass
    else:
        # 로컬은 복잡하니 생략하거나 pyttsx3 사용
        pass 

# -------------------- 클래스 --------------------
class Word:
    def __init__(self, word, meaning, x, y, speed):
        self.word = word
        self.meaning = meaning
        self.x = x
        self.y = y
        self.speed = speed
        self.active = True
        self.matched = False
        self.display_meaning_time = 0

    def update(self):
        if self.active:
            self.y += self.speed

    def draw(self, screen, font):
        if self.active and not self.matched:
            # 글자 테두리 (가독성 위해)
            text_surf = font.render(self.word, True, (255, 255, 255))
            screen.blit(text_surf, (self.x, self.y))

        if self.matched:
            # 뜻 보여주기
            import time
            if time.time() - self.display_meaning_time < 1.5:
                meaning_surf = font.render(self.meaning, True, (255, 200, 200))
                screen.blit(meaning_surf, (self.x, self.y))
            else:
                self.active = False

# -------------------- 메인 게임 --------------------
async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Google Sheet Typing Game")
    
    # 폰트 설정
    try:
        font = pygame.font.Font("meiryo.ttc", 20)
        ui_font = pygame.font.Font("meiryo.ttc", 24)
    except:
        font = pygame.font.Font(None, 30)
        ui_font = pygame.font.Font(None, 36)

    # ★ 게임 시작 전 데이터 로딩 대기 화면
    loading = True
    word_db = []
    
    # 로딩 화면 표시
    screen.fill((0,0,0))
    load_msg = ui_font.render("Loading Data from Google Sheet...", True, (255,255,255))
    screen.blit(load_msg, (50, SCREEN_HEIGHT//2))
    pygame.display.update()
    
    # 데이터 가져오기 (비동기)
    word_db = await fetch_csv_data(GOOGLE_SHEET_URL)
    
    if not word_db:
        # 데이터 로드 실패 시 비상용 더미 데이터
        word_db = [{"level":1, "word":"Error", "meaning":"데이터로드실패"}]

    # 타이틀 화면
    waiting = True
    start_msg = ui_font.render("Click or Press Key to Start", True, (0,255,0))
    
    while waiting:
        screen.fill((0,0,0))
        screen.blit(start_msg, (SCREEN_WIDTH//2 - 130, SCREEN_HEIGHT//2))
        pygame.display.update()
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.KEYDOWN:
                waiting = False
        await asyncio.sleep(0)

    # 게임 변수 초기화
    clock = pygame.time.Clock()
    running = True
    words = []
    input_text = ""
    lives = INITIAL_LIVES
    score = 0
    level = 1
    
    import time
    last_spawn_time = time.time() - 2 # 바로 시작

    while running:
        screen.fill((20, 20, 30)) # 약간 남색 배경
        
        # 레벨별 난이도 설정 (스테이지 테이블 대신 수식으로 처리)
        # 레벨이 오를수록 빨라지고(speed), 더 자주 나옴(interval 감소)
        spawn_interval = max(0.5, 2.0 - (level * 0.1))  # 2초에서 시작해서 점점 줄어듦
        fall_speed = 1.0 + (level * 0.2) # 1.0에서 시작해서 점점 빨라짐
        score_threshold = level * 100 # 다음 레벨까지 필요한 점수

        # 이벤트 처리
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    matched_any = False
                    for w in words:
                        if w.word == input_text and w.active and not w.matched:
                            w.matched = True
                            w.display_meaning_time = time.time()
                            speak_word(w.word)
                            score += 10
                            matched_any = True
                            break
                    input_text = ""
                    
                    # 레벨업 체크
                    if score >= score_threshold:
                        level += 1
                        print(f"Level Up! {level}")

                else:
                    input_text += event.unicode

        # 단어 생성 로직
        current_time = time.time()
        if current_time - last_spawn_time > spawn_interval:
            # 현재 레벨에 맞는 단어 필터링
            level_words = [w for w in word_db if w['level'] == level]
            
            # 해당 레벨 단어가 없으면 이전 레벨 단어들도 포함 (안전장치)
            if not level_words:
                level_words = [w for w in word_db if w['level'] <= level]
            
            if level_words:
                w_data = random.choice(level_words)
                x_pos = random.randint(20, SCREEN_WIDTH - 120)
                words.append(Word(w_data["word"], w_data["meaning"], x_pos, 0, fall_speed))
            
            last_spawn_time = current_time

        # 업데이트 및 그리기
        for w in words:
            w.update()
            w.draw(screen, font)
            
            # 화면 밖으로 나가면 라이프 감소
            if w.y > SCREEN_HEIGHT and w.active:
                w.active = False
                if not w.matched:
                    lives -= 1
                    # 화면 붉게 깜빡임 효과 (선택사항)

        # UI 표시
        input_ui = ui_font.render(f"> {input_text}", True, (0, 255, 0))
        screen.blit(input_ui, (50, SCREEN_HEIGHT - 60))

        info_ui = ui_font.render(f"Lv.{level}  Score: {score}  Lives: {lives}", True, (255, 255, 0))
        screen.blit(info_ui, (20, 20))

        # 게임오버 처리
        if lives <= 0:
            over_msg = ui_font.render("GAME OVER", True, (255, 0, 0))
            screen.blit(over_msg, (SCREEN_WIDTH//2 - 60, SCREEN_HEIGHT//2))
            pygame.display.update()
            await asyncio.sleep(3)
            # 재시작 또는 종료 로직 (여기선 종료)
            running = False

        pygame.display.update()
        await asyncio.sleep(0) # 웹 프레임 양보

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
