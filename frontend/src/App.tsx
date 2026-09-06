import { NavLink, Route, HashRouter as Router, Routes } from "react-router-dom";
import { Agents } from "./pages/Agents";
import { Automations } from "./pages/Automations";
import { Chat } from "./pages/Chat";
import { Dashboard } from "./pages/Dashboard";
import { Memory } from "./pages/Memory";
import { Tasks } from "./pages/Tasks";
import { Tools } from "./pages/Tools";
import { Voice } from "./pages/Voice";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`;

function App() {
  return (
    <Router>
      <nav className="flex flex-wrap gap-1 border-b border-slate-800 bg-[#0b0e14] px-4 py-2">
        <NavLink to="/" end className={navLinkClass}>
          Dashboard
        </NavLink>
        <NavLink to="/chat" className={navLinkClass}>
          Chat
        </NavLink>
        <NavLink to="/voice" className={navLinkClass}>
          Voice
        </NavLink>
        <NavLink to="/memory" className={navLinkClass}>
          Memory
        </NavLink>
        <NavLink to="/tools" className={navLinkClass}>
          Tools
        </NavLink>
        <NavLink to="/agents" className={navLinkClass}>
          Agents
        </NavLink>
        <NavLink to="/automations" className={navLinkClass}>
          Automations
        </NavLink>
        <NavLink to="/tasks" className={navLinkClass}>
          Tasks
        </NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/voice" element={<Voice />} />
        <Route path="/memory" element={<Memory />} />
        <Route path="/tools" element={<Tools />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/automations" element={<Automations />} />
        <Route path="/tasks" element={<Tasks />} />
      </Routes>
    </Router>
  );
}

export default App;
