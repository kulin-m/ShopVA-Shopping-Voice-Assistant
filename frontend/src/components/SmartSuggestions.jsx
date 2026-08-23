import React from 'react';
import { Lightbulb, Plus, History } from 'lucide-react';
import { api } from '../services/api';

export const SmartSuggestions = ({ suggestions, onItemAdded }) => {
  if (!suggestions || suggestions.length === 0) {
    return null;
  }

  const handleAddSuggestion = async (sug) => {
    try {
      await api.addShoppingItem({
        product_name: sug.product_name,
        quantity: 1,
        size: sug.suggested_size
      });
      onItemAdded();
    } catch (err) {
      console.error('Failed to add suggestion:', err);
    }
  };

  return (
    <div className="bg-gradient-to-br from-indigo-900 to-slate-900 rounded-2xl p-6 text-white shadow-md">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 bg-indigo-500/20 text-amber-300 rounded-xl border border-indigo-500/30">
          <Lightbulb className="w-6 h-6 animate-pulse" />
        </div>
        <div>
          <h3 className="text-lg font-bold">💡 Smart Suggestions</h3>
          <p className="text-xs text-indigo-200">Based on your co-purchase shopping history</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {suggestions.map((sug, idx) => (
          <div
            key={idx}
            className="bg-white/10 backdrop-blur-md border border-white/10 rounded-xl p-4 flex flex-col justify-between hover:bg-white/15 transition-all"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-bold text-white text-base">{sug.product_name}</span>
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-300 bg-amber-400/10 px-2 py-0.5 rounded-md border border-amber-400/20">
                  <History className="w-3 h-3" />
                  {sug.frequency_text}
                </span>
              </div>
              <p className="text-xs text-indigo-200 leading-relaxed mt-1">
                "{sug.reason}"
              </p>
            </div>

            <button
              onClick={() => handleAddSuggestion(sug)}
              className="mt-4 w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              Add {sug.product_name}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
