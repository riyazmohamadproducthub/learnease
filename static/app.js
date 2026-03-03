const lessonForm = document.getElementById('lesson-form');
const lessonEl = document.getElementById('lesson');
const quizEl = document.getElementById('quiz');
const historyList = document.getElementById('history-list');
const historyBtn = document.getElementById('refresh-history');

let activeSessionId = null;
let activeQuiz = [];

lessonForm.addEventListener('submit', async (event) => {
  event.preventDefault();

  const payload = {
    topic: document.getElementById('topic').value,
    methodology: document.getElementById('methodology').value,
    language: document.getElementById('language').value,
    visual: document.getElementById('visual').value,
  };

  const response = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    alert(data.error || 'Unable to create lesson.');
    return;
  }

  activeSessionId = data.session_id;
  activeQuiz = data.quiz;
  renderLesson(data.lesson);
  renderQuiz(activeQuiz);
  loadHistory();
});

function renderLesson(lesson) {
  lessonEl.classList.remove('hidden');
  lessonEl.innerHTML = `
    <h2>${lesson.title}</h2>
    <p><strong>Language:</strong> ${lesson.language} | <strong>Method:</strong> ${lesson.methodology} | <strong>Visual:</strong> ${lesson.visual_style}</p>
    <h3>Guided explanation</h3>
    <ol>${lesson.sections.map((s) => `<li>${s}</li>`).join('')}</ol>
    <h3>Key points</h3>
    <ul>${lesson.key_points.map((s) => `<li>${s}</li>`).join('')}</ul>
    <h3>Infographic: ${lesson.infographic.title}</h3>
    <div class="infographic">
      ${lesson.infographic.nodes.map((n) => `<div class="node"><strong>${n.label}</strong><div>${n.value}</div></div>`).join('')}
    </div>
  `;
}

function renderQuiz(quiz) {
  quizEl.classList.remove('hidden');
  quizEl.innerHTML = `
    <h2>Post-learning quiz</h2>
    <form id="quiz-form">
      ${quiz.map((q, i) => `
      <fieldset>
        <legend>${i + 1}. ${q.question}</legend>
        ${q.options.map((option, j) => `
          <label><input type="radio" name="q-${i}" value="${j}" required /> ${option}</label>
        `).join('')}
      </fieldset>
      `).join('')}
      <button type="submit">Submit quiz</button>
    </form>
    <div id="quiz-result"></div>
    <h3>Feedback for improvement</h3>
    <textarea id="feedback" rows="3" placeholder="What can improve this lesson?"></textarea>
    <button id="feedback-btn">Save feedback</button>
    <div id="feedback-status"></div>
  `;

  document.getElementById('quiz-form').addEventListener('submit', submitQuiz);
  document.getElementById('feedback-btn').addEventListener('click', saveFeedback);
}

async function submitQuiz(event) {
  event.preventDefault();
  const answers = activeQuiz.map((_, i) => Number(document.querySelector(`input[name="q-${i}"]:checked`).value));

  const response = await fetch('/api/submit-quiz', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: activeSessionId, answers }),
  });
  const result = await response.json();

  document.getElementById('quiz-result').innerHTML = `<p><strong>Score:</strong> ${result.score}% - ${result.message}</p>`;
  loadHistory();
}

async function saveFeedback() {
  const feedback = document.getElementById('feedback').value;
  if (!activeSessionId) return;

  const response = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: activeSessionId, feedback }),
  });

  const data = await response.json();
  document.getElementById('feedback-status').textContent = response.ok ? 'Feedback saved.' : data.error;
  loadHistory();
}

async function loadHistory() {
  const response = await fetch('/api/history');
  const history = await response.json();
  historyList.innerHTML = history.length
    ? history.map((h) => `<li><strong>${h.topic}</strong> | ${h.language} | ${h.methodology} | score: ${h.score ?? 'N/A'} | ${new Date(h.created_at).toLocaleString()}</li>`).join('')
    : '<li>No history yet for this device.</li>';
}

historyBtn.addEventListener('click', loadHistory);
loadHistory();
