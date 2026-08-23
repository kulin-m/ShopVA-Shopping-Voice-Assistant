import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Signup from './components/Signup';
import { VoiceToggle } from './components/VoiceToggle';
import { ShoppingList } from './components/ShoppingList';
import { SmartSuggestions } from './components/SmartSuggestions';
import { api } from './services/api';
import { ShoppingCart, CheckCircle, RefreshCw, LogOut, User as UserIcon } from 'lucide-react';

function Dashboard() {
  const { user, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [voiceState, setVoiceState] = useState('OFF');
  const [lastTranscript, setLastTranscript] = useState('');
  const [toastMessage, setToastMessage] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchShoppingListAndSuggestions = async () => {
    try {
      setLoading(true);
      const listData = await api.getShoppingList();
      setItems(listData.items || []);

      const sugData = await api.getSmartSuggestions();
      setSuggestions(sugData.suggestions || []);
    } catch (err) {
      console.error('Error fetching shopping list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchShoppingListAndSuggestions();
  }, []);

  const handleCommandProcessed = (response) => {
    if (response.message) {
      setToastMessage(response.message);
      setTimeout(() => setToastMessage(null), 4000);
    }
    fetchShoppingListAndSuggestions();
  };

  const handleCheckout = async () => {
    try {
      const res = await api.checkoutList();
      if (res.message) {
        setToastMessage(res.message);
        setTimeout(() => setToastMessage(null), 4000);
      }
      fetchShoppingListAndSuggestions();
    } catch (err) {
      console.error('Checkout failed:', err);
    }
  };

  const handleLogoutClick = () => {
    setVoiceState('OFF');
    logout();
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans pb-16">
      {/* Top Navbar */}
      <header className="bg-slate-900 text-white shadow-md sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600 rounded-xl">
              <ShoppingCart className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-extrabold tracking-tight">Voice Shopping Assistant</h1>
              <p className="text-xs text-indigo-300">Intelligent Voice-First Shopping List</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-xl text-xs text-slate-300 border border-slate-700">
              <UserIcon className="w-4 h-4 text-indigo-400" />
              <span className="font-medium text-white">{user?.name || user?.email}</span>
            </div>

            <button
              onClick={fetchShoppingListAndSuggestions}
              className="p-2 hover:bg-slate-800 rounded-xl transition-colors text-slate-300 hover:text-white"
              title="Refresh List"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={handleLogoutClick}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/90 hover:bg-red-600 text-white rounded-xl text-xs font-semibold transition-colors shadow-sm"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-4xl mx-auto px-4 mt-6 space-y-6">
        {/* Toast Feedback */}
        {toastMessage && (
          <div className="bg-emerald-600 text-white px-4 py-3 rounded-xl shadow-lg flex items-center justify-between animate-fade-in">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <CheckCircle className="w-5 h-5 flex-shrink-0" />
              <span>{toastMessage}</span>
            </div>
          </div>
        )}

        {/* Voice Toggle Component */}
        <VoiceToggle
          onCommandProcessed={handleCommandProcessed}
          voiceState={voiceState}
          setVoiceState={setVoiceState}
          lastTranscript={lastTranscript}
          setLastTranscript={setLastTranscript}
        />

        {/* Smart Suggestions Component */}
        <SmartSuggestions
          suggestions={suggestions}
          onItemAdded={fetchShoppingListAndSuggestions}
        />

        {/* Shopping List Component */}
        <ShoppingList
          items={items}
          onItemUpdated={fetchShoppingListAndSuggestions}
          onCheckout={handleCheckout}
        />
      </main>
    </div>
  );
}

function MainApp() {
  const { user, loading } = useAuth();
  const [authView, setAuthView] = useState('login');

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex items-center gap-3 text-slate-600 font-semibold">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
          <span>Validating session...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return authView === 'login' ? (
      <Login onSwitchToSignup={() => setAuthView('signup')} />
    ) : (
      <Signup onSwitchToLogin={() => setAuthView('login')} />
    );
  }

  return <Dashboard />;
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
