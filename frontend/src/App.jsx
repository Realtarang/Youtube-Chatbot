import { Navigate, Route, Routes } from 'react-router-dom'

import Navbar from './components/Navbar.jsx'
import Chat from './pages/Chat.jsx'
import History from './pages/History.jsx'
import Home from './pages/Home.jsx'

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-body">
      <Navbar />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat/:videoId" element={<Chat />} />
          <Route path="/history" element={<History />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  )
}
