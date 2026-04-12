import { BrowserRouter, Routes, Route } from "react-router-dom"
import Landing from "./pages/Landing"
import Scanning from "./pages/Scanning"
import Report from "./pages/Report"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/scanning" element={<Scanning />} />
        <Route path="/report" element={<Report />} />
      </Routes>
    </BrowserRouter>
  )
}
