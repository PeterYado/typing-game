import pygame
import random
import sys
import asyncio
import io
import csv
import time

# -------------------- 설정 --------------------
# ★ 구글 시트 주소 (CSV)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSjim8tnfOemk_eCrfikI5jl105bSbpv2uMP0ZZNPZJOHbKZIY2j_tvhIo3xIi7LVqSHz1gYTEHt6f1/pub?gid=0&single=true&output=csv"

SCREEN_WIDTH = 540
SCREEN_HEIGHT = 900
FPS = 60
IS_WEB = sys.platform == "emscripten"

# -------------------- 화면 출력 로그 함수 --------------------
# 콘솔 대신 게임 화면에 글자를 적어주는 함수입니다.
def log_to_screen(screen, font, message):
    screen.fill((0, 0, 0))
    # 메시지를 줄바꿈해서 출력
    lines = message.split('\n')
    y = SCREEN_HEIGHT // 3
    for line in lines:
        text = font.render(line, True, (255, 255, 255))
        screen.blit(text, (20, y))
        y += 30
    pygame.display.update()

# -------------------- 데이터 로드 (디버깅 강화) --------------------
async def fetch_csv_data(url, screen, font):
    log_to_screen(screen, font, "1. 네트워크 초기화 중...")
    await asyncio.sleep(0.5) # 화면 갱신 대기

    csv_text = ""
    
    # 우회 주소 생성
    import urllib.parse
    encoded_url = urllib.parse.quote(url, safe='')
    proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
    target_url = proxy_url if IS_WEB else url
    
    log_to_screen(screen, font, f"2. 데이터 요청 시작...\n{target_url[:40]}...")
    
    try:
        if IS_WEB:
            from pyodide.http import pyfetch
            response = await pyfetch(target_url)
            if response.status == 200:
                csv_text = await response.string()
                log_to_screen(screen, font, "3. 다운로드 성공!")
            else:
                log_to_screen(screen, font, f"3. 실패! 상태코드: {response.status}")
                await asyncio.sleep(2)
        else:
            # 로컬 테스트용
            import requests
            response = requests.get(url)
            csv_text = response.text
            
    except Exception as e:
        log_to_screen(screen, font, f"3. 에러 발생!\n{str(e)}")
        print(f"Error: {e}")
        await asyncio.sleep(3) # 에러 메시지 읽을 시간 줌

    # 파싱 시작
    log_to_screen(screen, font, "4. 데이터 분석 중...")
    parsed_data = []
    
    if csv_text:
        try:
            f = io.StringIO(csv_text)
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('level') and row.get('word'):
                    parsed_data.append({
                        "level": int(row['level']),
                        "word": row['word'].strip(),
                        "meaning": row['meaning'].strip()
                    })
            log_to_screen(screen, font, f"5. 완료! 총 {len(parsed_data)}개 로드됨")
            await asyncio.sleep(1)
        except Exception as e:
            log_to_screen(screen, font, f"4. CSV 파싱 실패\n{str(e)}")
            await asyncio.sleep(3)
    
    return parsed_data

# -------------------- 메인 --------------------
async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    
    # 폰트 로드 (한글 깨짐 방지 위해 없으면 기본폰트)
    try:
        font = pygame.font.Font("meiryo.ttc", 20)
    except:
        font = pygame.font.Font(None, 24)

    # 데이터 로드 시도
    word_db = []
    try:
        # 화면과 폰트를 넘겨줘서 진행상황을 그리게 함
        word_db = await fetch_csv_data(GOOGLE_SHEET_URL, screen, font)
    except Exception as e:
        log_to_screen(screen, font, f"치명적 오류:\n{e}")
        await asyncio.sleep(3)

    # 실패 시 기본 데이터 사용
    if not word_db:
        log_to_screen(screen, font, "기본 데이터로 시작합니다.")
        await asyncio.sleep(1)
        word_db = [{"level":1, "word":"Error", "meaning":"데이터로드실패"},
                   {"level":1, "word":"Check", "meaning":"확인요망"}]

    # === 여기서부터 게임 루프 ===
    # (기존 코드와 동일하게 게임 시작)
    
    # 폰트 다시 설정 (게임용)
    try:
        game_font = pygame.font.Font("meiryo.ttc", 20)
        ui_font = pygame.font.Font("meiryo.ttc", 24)
    except:
        game_font = pygame.font.Font(None, 30)
        ui_font = pygame.font.Font(None, 36)

    clock = pygame.time.Clock()
    running = True
    words = []
    input_text = ""
    lives = 3
    score = 0
    level = 1
    last_spawn_time = time.time() - 2

    class Word:
        def __init__(self, word, meaning, x, y, speed):
            self.word = word; self.meaning = meaning
            self.x = x; self.y = y; self.speed = speed
            self.active = True; self.matched = False; self.display_time = 0
        def update(self):
            if self.active: self.y += self.speed
        def draw(self, screen):
            if self.active and not self.matched:
                s = game_font.render(self.word, True, (255,255,255))
                screen.blit(s, (self.x, self.y))
            if self.matched:
                if time.time() - self.display_time < 1.0:
                    s = game_font.render(self.meaning, True, (255,200,200))
                    screen.blit(s, (self.x, self.y))
                else: self.active = False

    # 게임 루프
    while running:
        screen.fill((20, 20, 30))
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_BACKSPACE: input_text = input_text[:-1]
                elif event.key == pygame.K_RETURN:
                    matched = False
                    for w in words:
                        if w.word == input_text and w.active and not w.matched:
                            w.matched = True; w.display_time = time.time()
                            score += 10; matched = True; break
                    input_text = ""
                else: input_text += event.unicode

        # 스폰
        spawn_interval = max(0.5, 2.0 - (level * 0.1))
        if time.time() - last_spawn_time > spawn_interval:
            candidates = [w for w in word_db if w['level'] == level]
            if not candidates: candidates = word_db
            
            if candidates:
                d = random.choice(candidates)
                words.append(Word(d['word'], d['meaning'], random.randint(20, SCREEN_WIDTH-100), 0, 1.0 + level*0.2))
            last_spawn_time = time.time()

        # 그리기
        for w in words:
            w.update(); w.draw(screen)
            if w.y > SCREEN_HEIGHT and w.active:
                w.active = False
                if not w.matched: lives -= 1

        # UI
        screen.blit(ui_font.render(f"> {input_text}", True, (0,255,0)), (50, SCREEN_HEIGHT-50))
        screen.blit(ui_font.render(f"Lv.{level} Score:{score} Lives:{lives}", True, (255,255,0)), (20,20))

        if lives <= 0:
            screen.blit(ui_font.render("GAME OVER", True, (255,0,0)), (SCREEN_WIDTH//2-60, SCREEN_HEIGHT//2))
            pygame.display.update()
            await asyncio.sleep(3)
            running = False

        pygame.display.update()
        await asyncio.sleep(0)

    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())
