import { useEffect, useState } from 'react';
import Auth from './Auth';
import { apiRequest } from './api';

const sampleMessages = [
  {
    id: 1,
    sender: 'assistant',
    text: 'Hello! I am your care assistant. Tell me what you need or describe your symptoms.',
  },
];

const quickActions = [
  'Book appointment',
  'Talk to doctor',
  'Reception help',
  'Symptoms check',
];

const emptyForm = {
  doctor_name: '',
  department: 'General Medicine',
  appointment_date: '',
  appointment_time: '09:00',
  notes: '',
};

function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('saad_user');
    return stored ? JSON.parse(stored) : null;
  });
  const [messages, setMessages] = useState(sampleMessages);
  const [draft, setDraft] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [appointments, setAppointments] = useState([]);
  const [chatSessions, setChatSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatDraft, setChatDraft] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [view, setView] = useState('dashboard');
  const [bookingForm, setBookingForm] = useState(emptyForm);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingMessage, setBookingMessage] = useState('');

  useEffect(() => {
    if (!user) return;

    const loadAppointments = async () => {
      try {
        const result = await apiRequest('/appointments/');
        setAppointments(result || []);
      } catch (error) {
        console.error('Failed to load appointments', error);
      }
    };

    const loadChatSessions = async () => {
      try {
        const result = await apiRequest('/chat-sessions/');
        setChatSessions(result || []);
        if (!selectedSessionId && result.length > 0) {
          setSelectedSessionId(result[0].id);
        }
      } catch (error) {
        console.error('Failed to load chat sessions', error);
      }
    };

    loadAppointments();
    loadChatSessions();
  }, [user]);

  useEffect(() => {
    if (!selectedSessionId) {
      setChatMessages([]);
      return;
    }

    const loadChatMessages = async () => {
      try {
        const result = await apiRequest('/chat-messages/');
        const filtered = (result || []).filter((message) => message.session === selectedSessionId);
        setChatMessages(filtered);
      } catch (error) {
        console.error('Failed to load chat messages', error);
      }
    };

    loadChatMessages();
  }, [selectedSessionId]);

  const sendMessage = async (messageText = draft) => {
    const trimmed = messageText.trim();
    if (!trimmed || isLoading) return;

    const patientMessage = {
      id: Date.now(),
      sender: 'patient',
      text: trimmed,
    };

    setMessages((prev) => [...prev, patientMessage]);
    setDraft('');
    setIsLoading(true);

    try {
      const data = await apiRequest('/ai-triage/', {
        method: 'POST',
        body: JSON.stringify({ message: trimmed }),
      });

      const summaryData = await apiRequest('/ai-summary/', {
        method: 'POST',
        body: JSON.stringify({
          symptoms: trimmed,
          context: `Patient reported: ${trimmed}`,
          route: data.route,
        }),
      });

      const botResponse = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: `${data.recommendation}\n\nSummary: ${summaryData.summary}\n\nRoute: ${data.route}\nUrgency: ${data.urgency}`,
      };

      setMessages((prev) => [...prev, botResponse]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          sender: 'assistant',
          text: 'I could not reach the server right now. Please try again in a moment.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAction = (action) => {
    setDraft(action);
    sendMessage(action);
  };

  const handleSendDoctorMessage = async () => {
    if (!selectedSessionId || !chatDraft.trim() || chatSending) return;

    setChatSending(true);
    try {
      const payload = {
        session: selectedSessionId,
        sender: 'doctor',
        message: chatDraft.trim(),
      };

      const created = await apiRequest('/chat-messages/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setChatMessages((prev) => [...prev, created]);
      setChatDraft('');
    } catch (error) {
      console.error('Failed to send doctor message', error);
    } finally {
      setChatSending(false);
    }
  };

  const handleBookingChange = (event) => {
    const { name, value } = event.target;
    setBookingForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleBookAppointment = async (event) => {
    event.preventDefault();
    setBookingLoading(true);
    setBookingMessage('');

    try {
      const payload = {
        doctor_name: bookingForm.doctor_name || 'Dr. Samir Khan',
        department: bookingForm.department,
        appointment_date: bookingForm.appointment_date,
        appointment_time: bookingForm.appointment_time,
        notes: bookingForm.notes || 'Patient requested follow-up consultation.',
      };

      const created = await apiRequest('/appointments/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setAppointments((prev) => [created, ...prev]);
      setBookingForm(emptyForm);
      setView('dashboard');
      setBookingMessage('Appointment booked successfully.');
    } catch (error) {
      setBookingMessage(error.message || 'Unable to book this appointment.');
    } finally {
      setBookingLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('saad_token');
    localStorage.removeItem('saad_user');
    setUser(null);
  };

  if (!user) {
    return <Auth onAuth={setUser} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">+</div>
          <div>
            <p className="eyebrow">SAAD</p>
            <h1>Kampala Community Health Clinic</h1>
          </div>
        </div>

        <nav className="nav">
          <button className={view === 'dashboard' ? 'nav-item active' : 'nav-item'} onClick={() => setView('dashboard')}>Dashboard</button>
          <button className={view === 'booking' ? 'nav-item active' : 'nav-item'} onClick={() => setView('booking')}>Book Visit</button>
          <button className={view === 'reception' ? 'nav-item active' : 'nav-item'} onClick={() => setView('reception')}>Reception</button>
          <button className={view === 'doctor' ? 'nav-item active' : 'nav-item'} onClick={() => setView('doctor')}>Doctor Queue</button>
        </nav>

        <div className="summary-card">
          <p className="label">AI Triage Status</p>
          <h3>Online</h3>
          <span>Priority review enabled</span>
        </div>

        <button className="logout-btn" onClick={handleLogout}>Logout</button>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow muted">Kampala Community Health Clinic</p>
            <h2>Welcome, {user.first_name || user.username}</h2>
          </div>
          <button className="primary-btn" onClick={() => setView('booking')}>New case</button>
        </header>

        <section className="quick-actions">
          {quickActions.map((action) => (
            <button key={action} className="chip" onClick={() => handleQuickAction(action)}>
              {action}
            </button>
          ))}
        </section>

        {view === 'dashboard' && (
          <>
            <section className="dashboard-grid">
              <div className="panel-card">
                <h3>Upcoming appointments</h3>
                {appointments.length === 0 ? (
                  <p className="empty-state">No appointments yet.</p>
                ) : (
                  <ul className="appointment-list">
                    {appointments.slice(0, 3).map((appointment) => (
                      <li key={appointment.id}>
                        <strong>{appointment.doctor_name}</strong>
                        <span>{appointment.department_name}</span>
                        <small>
                          {appointment.appointment_datetime_display}
                        </small>
                        <small className="status-pill">{appointment.status}</small>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="panel-card">
                <h3>Quick actions</h3>
                <div className="small-actions">
                  <button className="small-btn" onClick={() => setView('booking')}>Book consultation</button>
                  <button className="small-btn" onClick={() => setView('reception')}>View reception queue</button>
                  <button className="small-btn" onClick={() => setView('doctor')}>Doctor review list</button>
                </div>
              </div>
            </section>

            <section className="chat-card">
              <div className="chat-header">
                <div>
                  <p className="eyebrow muted">Care Assistant</p>
                  <h3>Smart Intake Chat</h3>
                </div>
                <span className="status-pill online">online</span>
              </div>

              <div className="messages">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`message-row ${message.sender === 'patient' ? 'patient' : 'assistant'}`}
                  >
                    <div className="bubble">
                      {message.text}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="message-row assistant">
                    <div className="bubble">Assessing your request...</div>
                  </div>
                )}
              </div>

              <div className="composer">
                <input
                  type="text"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                  placeholder="Type your message here..."
                />
                <button onClick={() => sendMessage()} disabled={isLoading}>
                  {isLoading ? 'Sending...' : 'Send'}
                </button>
              </div>
            </section>
          </>
        )}

        {view === 'booking' && (
          <section className="panel-card form-card">
            <h3>Book an appointment</h3>
            <form onSubmit={handleBookAppointment} className="booking-form">
              <label>
                Doctor
                <input name="doctor_name" value={bookingForm.doctor_name} onChange={handleBookingChange} placeholder="Dr. Samir Khan" />
              </label>

              <label>
                Department
                <select name="department" value={bookingForm.department} onChange={handleBookingChange}>
                  <option value="General Medicine">General Medicine</option>
                  <option value="Cardiology">Cardiology</option>
                  <option value="Dermatology">Dermatology</option>
                  <option value="Pediatrics">Pediatrics</option>
                </select>
              </label>

              <label>
                Date
                <input type="date" name="appointment_date" value={bookingForm.appointment_date} onChange={handleBookingChange} required />
              </label>

              <label>
                Time
                <input type="time" name="appointment_time" value={bookingForm.appointment_time} onChange={handleBookingChange} required />
              </label>

              <label>
                Notes
                <textarea name="notes" value={bookingForm.notes} onChange={handleBookingChange} placeholder="Describe concerns or symptoms" />
              </label>

              {bookingMessage && <div className="info-box">{bookingMessage}</div>}

              <button type="submit" className="primary-btn" disabled={bookingLoading}>
                {bookingLoading ? 'Booking...' : 'Book visit'}
              </button>
            </form>
          </section>
        )}

        {view === 'reception' && (
          <section className="panel-card">
            <h3>Reception intake queue</h3>
            <div className="queue-grid">
              {appointments.length === 0 ? (
                <p className="empty-state">No intake records available yet.</p>
              ) : (
                appointments.map((appointment) => (
                  <div key={appointment.id} className="queue-item">
                    <strong>{appointment.patient_name}</strong>
                    <span>{appointment.department_name}</span>
                    <small>{appointment.doctor_name}</small>
                    <small>{appointment.appointment_datetime_display}</small>
                    <small>Status: {appointment.status}</small>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        {view === 'doctor' && (
          <section className="panel-card doctor-chat-panel">
            <h3>Doctor review queue</h3>
            <div className="doctor-chat">
              <div className="session-list">
                {chatSessions.length === 0 ? (
                  <p className="empty-state">No active sessions yet.</p>
                ) : (
                  chatSessions.map((session) => (
                    <button
                      key={session.id}
                      className={selectedSessionId === session.id ? 'session-item active' : 'session-item'}
                      onClick={() => setSelectedSessionId(session.id)}
                    >
                      <strong>{session.session_type}</strong>
                      <small>Session #{session.id}</small>
                    </button>
                  ))
                )}
              </div>

              <div className="chat-thread">
                <div className="thread-header">
                  <strong>{chatSessions.find((session) => session.id === selectedSessionId)?.session_type || 'No session selected'}</strong>
                </div>

                <div className="thread-messages">
                  {chatMessages.length === 0 ? (
                    <p className="empty-state">No chat messages in this thread yet.</p>
                  ) : (
                    chatMessages.map((message) => (
                      <div key={message.id} className={message.sender === 'assistant' ? 'thread-message assistant' : 'thread-message patient'}>
                        <span>{message.sender == 'patient' ? 'You' : 'AI Assistant'}</span>
                        <p>{message.message}</p>
                      </div>
                    ))
                  )}
                </div>

                <div className="thread-composer">
                  <input
                    type="text"
                    value={chatDraft}
                    onChange={(e) => setChatDraft(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendDoctorMessage()}
                    placeholder="Write a response to the patient..."
                  />
                  <button onClick={handleSendDoctorMessage} disabled={chatSending}>
                    {chatSending ? 'Sending...' : 'Reply'}
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
