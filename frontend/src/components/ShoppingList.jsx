import React, { useState, useMemo } from 'react';
import { Plus, Trash2, CheckCircle2, Circle, AlertTriangle, ChevronDown, ShoppingBag, Sparkles, Layers, Tag } from 'lucide-react';
import { api } from '../services/api';

export const ShoppingList = ({ items, onItemUpdated, onCheckout }) => {
  const [newItemName, setNewItemName] = useState('');
  const [isCategorySorted, setIsCategorySorted] = useState(false);
  const [selectedProductSizes, setSelectedProductSizes] = useState(null);
  const [activeSizeModalItemId, setActiveSizeModalItemId] = useState(null);
  const [loadingItemId, setLoadingItemId] = useState(null);

  const handleManualAdd = async (e) => {
    e.preventDefault();
    if (!newItemName.trim()) return;

    try {
      await api.addShoppingItem({ product_name: newItemName.trim(), quantity: 1 });
      setNewItemName('');
      onItemUpdated();
    } catch (err) {
      console.error('Failed to manually add item:', err);
    }
  };

  const handleQuantityChange = async (item, delta) => {
    const newQty = item.quantity + delta;
    if (newQty <= 0) {
      handleDeleteItem(item.id);
      return;
    }

    try {
      setLoadingItemId(item.id);
      await api.updateShoppingItem(item.id, { quantity: newQty });
      onItemUpdated();
    } finally {
      setLoadingItemId(null);
    }
  };

  const handleDeleteItem = async (itemId) => {
    try {
      setLoadingItemId(itemId);
      await api.deleteShoppingItem(itemId);
      onItemUpdated();
    } finally {
      setLoadingItemId(null);
    }
  };

  const handleToggleStatus = async (item) => {
    const newStatus = item.status === 'PURCHASED' ? 'PENDING' : 'PURCHASED';
    try {
      setLoadingItemId(item.id);
      await api.updateShoppingItem(item.id, { status: newStatus });
      onItemUpdated();
    } finally {
      setLoadingItemId(null);
    }
  };

  const openSizeSelector = async (item) => {
    setActiveSizeModalItemId(item.id);
    setSelectedProductSizes(['340ml', '500ml', '650ml', '1L', '250g', '500g']); // Default options

    if (item.product_id) {
      try {
        const sizes = await api.getProductSizes(item.product_id);
        if (sizes && sizes.length > 0) {
          setSelectedProductSizes(sizes.map(s => s.size_value));
        }
      } catch (e) {
        console.warn('Failed to fetch sizes:', e);
      }
    }
  };

  const selectSize = async (itemId, size) => {
    try {
      setLoadingItemId(itemId);
      await api.resolveItemSize(itemId, size);
      setActiveSizeModalItemId(null);
      onItemUpdated();
    } finally {
      setLoadingItemId(null);
    }
  };

  const categoryGroups = useMemo(() => {
    if (!isCategorySorted) return null;
    const groups = {};
    items.forEach(item => {
      const cat = item.category || 'Other';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(item);
    });
    return groups;
  }, [items, isCategorySorted]);

  const renderItemRow = (item) => {
    const isPurchased = item.status === 'PURCHASED';
    const isUnresolved = item.is_size_unresolved;

    return (
      <div
        key={item.id}
        className={`flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border transition-all ${
          isPurchased
            ? 'bg-slate-50 border-slate-200 opacity-60'
            : isUnresolved
            ? 'bg-amber-50/50 border-amber-200 shadow-sm'
            : 'bg-white border-slate-200 hover:border-slate-300'
        }`}
      >
        {/* Item Details */}
        <div className="flex items-center gap-3 mb-2 sm:mb-0">
          <button
            onClick={() => handleToggleStatus(item)}
            className="text-slate-400 hover:text-emerald-600 transition-colors"
          >
            {isPurchased ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            ) : (
              <Circle className="w-5 h-5" />
            )}
          </button>

          <div>
            <span className={`font-semibold text-slate-800 ${isPurchased ? 'line-through' : ''}`}>
              {item.product_name}
            </span>

            {/* Size display & Unresolved selector */}
            <div className="inline-flex items-center ml-3">
              {isUnresolved ? (
                <div className="relative inline-block">
                  <button
                    onClick={() => openSizeSelector(item)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-100 border border-amber-300 text-amber-900 rounded-lg text-xs font-bold hover:bg-amber-200 transition-all shadow-sm"
                  >
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-700" />
                    <span>{item.size || 'Select size'}</span>
                    <ChevronDown className="w-3 h-3 text-amber-700" />
                  </button>

                  {/* Size Selection Dropdown Modal */}
                  {activeSizeModalItemId === item.id && (
                    <div className="absolute left-0 mt-1 z-30 w-44 bg-white border border-slate-200 rounded-xl shadow-xl p-2 space-y-1">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-2 py-1">
                        Select Size
                      </p>
                      {selectedProductSizes.map((sz) => (
                        <button
                          key={sz}
                          onClick={() => selectSize(item.id, sz)}
                          className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 transition-colors"
                        >
                          {sz}
                        </button>
                      ))}
                      <button
                        onClick={() => setActiveSizeModalItemId(null)}
                        className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-slate-600 pt-1 border-t"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                item.size && (
                  <span className="px-2 py-0.5 bg-slate-100 border border-slate-200 text-slate-700 rounded-md text-xs font-medium">
                    {item.size}
                  </span>
                )
              )}
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between sm:justify-end gap-3">
          <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden bg-slate-50">
            <button
              onClick={() => handleQuantityChange(item, -1)}
              className="px-2.5 py-1 hover:bg-slate-200 text-slate-600 font-bold text-xs"
            >
              -
            </button>
            <span className="px-3 py-1 font-bold text-xs text-slate-800 bg-white border-x border-slate-200">
              {item.quantity} {item.unit || ''}
            </span>
            <button
              onClick={() => handleQuantityChange(item, 1)}
              className="px-2.5 py-1 hover:bg-slate-200 text-slate-600 font-bold text-xs"
            >
              +
            </button>
          </div>

          <button
            onClick={() => handleDeleteItem(item.id)}
            className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
            title="Remove item"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-50 rounded-xl text-indigo-600">
            <ShoppingBag className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-800">Shopping List</h2>
            <p className="text-xs text-slate-500">{items.length} items total</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* According to Category Toggle Button */}
          <button
            onClick={() => setIsCategorySorted(!isCategorySorted)}
            className={`px-3 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-2 shadow-sm ${
              isCategorySorted
                ? 'bg-indigo-600 border-indigo-600 text-white ring-2 ring-indigo-200'
                : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
            }`}
            title="Toggle Category Grouping"
          >
            <Layers className="w-4 h-4" />
            <span>According to category</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-extrabold ${
              isCategorySorted ? 'bg-indigo-700 text-white' : 'bg-slate-200 text-slate-600'
            }`}>
              {isCategorySorted ? 'ON' : 'OFF'}
            </span>
          </button>

          {items.length > 0 && (
            <button
              onClick={onCheckout}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-sm font-semibold transition-all shadow-sm flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-amber-400" />
              Complete Purchase
            </button>
          )}
        </div>
      </div>

      {/* Manual Input Form */}
      <form onSubmit={handleManualAdd} className="flex items-center gap-2 mb-6">
        <input
          type="text"
          value={newItemName}
          onChange={(e) => setNewItemName(e.target.value)}
          placeholder="Type an item (e.g. Shampoo, Milk)..."
          className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
        />
        <button
          type="submit"
          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold transition-all flex items-center gap-1 shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add
        </button>
      </form>

      {/* Items List */}
      {items.length === 0 ? (
        <div className="text-center py-12 bg-slate-50 rounded-xl border border-dashed border-slate-200">
          <ShoppingBag className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-600 font-medium text-sm">Your shopping list is currently empty</p>
          <p className="text-xs text-slate-400 mt-1">Use voice mode or the input box above to add items</p>
        </div>
      ) : isCategorySorted && categoryGroups ? (
        /* Grouped by Category (ON) */
        <div className="space-y-6">
          {Object.entries(categoryGroups).map(([catName, groupItems]) => (
            <div key={catName} className="space-y-2">
              <div className="flex items-center gap-2 pb-1.5 border-b border-indigo-100 text-indigo-900">
                <Tag className="w-4 h-4 text-indigo-600" />
                <h3 className="text-xs font-extrabold uppercase tracking-wider text-indigo-950">{catName}</h3>
                <span className="text-[11px] font-bold text-indigo-400">({groupItems.length})</span>
              </div>
              <div className="space-y-3">
                {groupItems.map((item) => renderItemRow(item))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Normal Flat Order (OFF) */
        <div className="space-y-3">
          {items.map((item) => renderItemRow(item))}
        </div>
      )}
    </div>
  );
};
