import { useState, useRef, useEffect } from 'react'
import { Search, ChevronDown, X, Loader2 } from 'lucide-react'

export interface SelectOption {
  id: string
  name: string
  description?: string
  contextLength?: number
  pricing?: {
    prompt?: string
    completion?: string
  }
}

interface SearchableSelectProps {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
  isLoading?: boolean
  disabled?: boolean
  error?: string
}

export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = "Select an option...",
  isLoading = false,
  disabled = false,
  error,
}: SearchableSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Filter options based on search
  const filteredOptions = options.filter(option =>
    option.name.toLowerCase().includes(search.toLowerCase()) ||
    option.id.toLowerCase().includes(search.toLowerCase()) ||
    option.description?.toLowerCase().includes(search.toLowerCase())
  )

  // Get selected option
  const selectedOption = options.find(opt => opt.id === value)

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setSearch('')
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Focus input when opening
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const handleSelect = (optionId: string) => {
    onChange(optionId)
    setIsOpen(false)
    setSearch('')
  }

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange('')
    setSearch('')
  }

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          w-full flex items-center justify-between gap-2 px-3 py-2
          bg-gray-700 border rounded-lg text-left
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-600 cursor-pointer'}
          ${error ? 'border-red-500' : 'border-gray-600'}
          ${isOpen ? 'ring-2 ring-blue-500 border-transparent' : ''}
        `}
      >
        <span className={selectedOption ? 'text-white' : 'text-gray-400'}>
          {isLoading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading models...
            </span>
          ) : selectedOption ? (
            <span className="truncate">{selectedOption.name}</span>
          ) : (
            placeholder
          )}
        </span>
        <div className="flex items-center gap-1">
          {selectedOption && !disabled && (
            <X
              className="w-4 h-4 text-gray-400 hover:text-white"
              onClick={handleClear}
            />
          )}
          <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {error && (
        <p className="text-red-400 text-xs mt-1">{error}</p>
      )}

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-gray-800 border border-gray-600 rounded-lg shadow-xl overflow-hidden">
          {/* Search Input */}
          <div className="p-2 border-b border-gray-700">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search models..."
                className="w-full pl-9 pr-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Options List */}
          <div className="max-h-64 overflow-y-auto">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-center text-gray-400 text-sm">
                {search ? 'No models found' : 'No models available'}
              </div>
            ) : (
              filteredOptions.map((option) => (
                <button
                  key={option.id}
                  onClick={() => handleSelect(option.id)}
                  className={`
                    w-full px-3 py-2 text-left hover:bg-gray-700 transition-colors
                    ${option.id === value ? 'bg-blue-600/20 border-l-2 border-blue-500' : ''}
                  `}
                >
                  <div className="font-medium text-sm truncate">{option.name}</div>
                  {option.id !== option.name && (
                    <div className="text-xs text-gray-400 truncate">{option.id}</div>
                  )}
                  {(option.contextLength || option.description) && (
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                      {option.contextLength && (
                        <span>{(option.contextLength / 1000).toFixed(0)}K context</span>
                      )}
                      {option.description && (
                        <span className="truncate">{option.description.slice(0, 50)}</span>
                      )}
                    </div>
                  )}
                </button>
              ))
            )}
          </div>

          {/* Footer with count */}
          <div className="px-3 py-2 border-t border-gray-700 text-xs text-gray-400">
            {filteredOptions.length} of {options.length} models
          </div>
        </div>
      )}
    </div>
  )
}
