# 내 PC에서 Claude Code로 쓰기

PC에서 Claude Code를 열고 이 저장소 폴더에서 물어보면, Claude가 실시간 바이낸스 데이터로 직접 차트를 읽고 이 대화에서처럼 판단해 줘요. Claude Pro나 Max 구독이 필요해요(무료 플랜은 안 돼요).

## 1. 파이썬 설치 (한 번만)

1. https://www.python.org/downloads/ 에서 내려받아 설치해요.
2. 설치 첫 화면에서 **Add python.exe to PATH**를 꼭 체크해요.

## 2. 저장소 내려받기 (한 번만)

1. https://github.com/ta6546/kangneow 에 들어가요.
2. 초록색 **Code** 버튼 → **Download ZIP**을 눌러요.
3. 압축을 풀어 원하는 곳(예: `문서\kangneow`)에 둬요.

노트가 업데이트되면 같은 방법으로 다시 받으면 돼요. Git을 쓸 줄 알면 `git clone https://github.com/ta6546/kangneow` 후 `git pull`로 받아도 돼요.

## 3. Claude Code 설치 (한 번만)

둘 중 편한 방법을 고르세요.

**데스크톱 앱 (터미널이 낯설면 추천)**
1. https://claude.com/download 에서 Claude 데스크톱 앱을 설치하고 로그인해요.
2. 앱에서 **Code** 탭을 열고, 폴더 선택에서 2번에서 풀어 둔 `kangneow` 폴더를 고르세요.

**터미널**
1. 시작 메뉴에서 **PowerShell**을 열고 아래를 붙여 넣어요.
   ```
   irm https://claude.ai/install.ps1 | iex
   ```
2. PowerShell을 새로 열고 `claude --version`으로 설치를 확인해요.
3. 저장소 폴더로 이동해서 실행해요.
   ```
   cd $HOME\Documents\kangneow
   claude
   ```
4. 처음 실행하면 브라우저가 열리고 로그인하면 돼요.

## 3-1. 이 대화를 그대로 이어받기 (선택)

지금 클라우드 대화(세션 ID `session_01LuJ1YDoZP1xZYzfs1GwxBL`)를 대화 기록 그대로 PC로 가져올 수 있어요. 이렇게 하면 노트를 다시 읽지 않아도 지금까지의 대화를 그대로 기억한 채 이어서 물어볼 수 있어요.

1. https://git-scm.com/downloads/win 에서 Git for Windows를 설치해요. ZIP으로 받은 폴더는 이 방법에 쓸 수 없어요.
2. PowerShell에서 저장소를 git으로 받아요.
   ```
   cd $HOME\Documents
   git clone https://github.com/ta6546/kangneow
   cd kangneow
   ```
3. 이 대화를 가져와요. 지금 쓰는 claude.ai 계정으로 로그인돼 있어야 해요.
   ```
   claude --teleport session_01LuJ1YDoZP1xZYzfs1GwxBL
   ```
   세션 ID를 빼고 `claude --teleport`만 입력하면 목록에서 고를 수도 있어요.

가져온 뒤의 대화는 PC에만 남고, 클라우드 쪽 대화에는 반영되지 않아요. 대화가 아주 길어지면 Claude가 앞부분을 요약해서 기억하기 때문에, 중요한 내용은 지금처럼 노트에도 계속 남겨 두는 게 안전해요.

## 4. 물어보기

폴더를 열면 Claude가 `CLAUDE.md`를 읽고 이 프로젝트의 기준을 알고 시작해요.

- `/scan` : 지금 조건에 가까운 종목을 찾아 자세히 판단해요.
- `/check MUBARAK` : 코인 하나를 자세히 봐요.
- 그냥 말로 물어봐도 돼요. "AIN은 어때요?", "지금 괜찮아 보이는 거 있어?", "MUBARAK 0.08 뚫었는데 다시 봐줘"

처음 몇 번은 Claude가 파이썬 명령을 실행해도 되는지 물어봐요. 허용하면 돼요. 판단은 `docs/watchlist.md`에 날짜별로 쌓여서, 다음에 물어볼 때 이전 판단과 비교해 줘요.

## 참고

- 같은 Claude지만 이 대화 자체를 기억하지는 않아요. 대신 저장소의 노트와 관찰 기록을 읽고 이어서 판단해요.
- 결과는 매수·매도 추천이 아니라 강고양이님 기준에 대 본 판단이에요.
