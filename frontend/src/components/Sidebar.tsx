import { useState, useEffect } from 'react'
import { 
  PanelLeftClose, 
  PanelLeft, 
  Plus, 
  MessageSquare, 
  Trash2, 
  Loader2,
  Clock
} from 'lucide-react'
import { Conversation } from '../lib/types'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  currentConversationId: string | null
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
}

export default function Sidebar({
  isOpen,
  onToggle,
  currentConversationId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const fetchConversations = async () => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/conversations?limit=50')
      if (response.ok) {
        const data = await response.json()
        setConversations(data.conversations)
      }
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchConversations()
    }
  }, [isOpen])

  // Refresh conversations when a new one is created
  useEffect(() => {
    if (currentConversationId && isOpen) {
      fetchConversations()
    }
  }, [currentConversationId])

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    setDeletingId(id)
    try {
      const response = await fetch(`/api/conversations/${id}`, {
        method: 'DELETE',
      })
      if (response.ok) {
        setConversations(prev => prev.filter(c => c.id !== id))
        onDeleteConversation(id)
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    } finally {
      setDeletingId(null)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) {
      return 'Today'
    } else if (diffDays === 1) {
      return 'Yesterday'
    } else if (diffDays < 7) {
      return `${diffDays} days ago`
    } else {
      return date.toLocaleDateString()
    }
  }

  // Group conversations by date
  const groupedConversations = conversations.reduce((groups, conv) => {
    const dateKey = formatDate(conv.updated_at)
    if (!groups[dateKey]) {
      groups[dateKey] = []
    }
    groups[dateKey].push(conv)
    return groups
  }, {} as Record<string, Conversation[]>)

  return (
    <>
      {/* Toggle button when sidebar is closed */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="fixed left-3 top-3 z-50 p-2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-lg transition-colors"
          title="Open sidebar"
        >
          <PanelLeft className="w-5 h-5 text-gray-600 dark:text-gray-300" />
        </button>
      )}

      {/* Sidebar */}
      <div
        className={`fixed left-0 top-0 h-full bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 z-40 transition-all duration-300 ease-in-out ${
          isOpen ? 'w-72 translate-x-0' : 'w-72 -translate-x-full'
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Chat History</h2>
          <button
            onClick={onToggle}
            className="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="Close sidebar"
          >
            <PanelLeftClose className="w-5 h-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={onNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-500 dark:text-gray-400" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8 px-4">
              <MessageSquare className="w-10 h-10 text-gray-400 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No conversations yet</p>
              <p className="text-xs text-gray-400 dark:text-gray-600 mt-1">Start a new chat to begin</p>
            </div>
          ) : (
            Object.entries(groupedConversations).map(([dateKey, convs]) => (
              <div key={dateKey} className="mb-4">
                <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-gray-500">
                  <Clock className="w-3 h-3" />
                  {dateKey}
                </div>
                {convs.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => onSelectConversation(conv.id)}
                    className={`w-full flex items-start gap-2 px-3 py-2.5 rounded-lg text-left transition-colors group ${
                      currentConversationId === conv.id
                        ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white'
                        : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                  >
                    <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-500" />
                    <span className="flex-1 text-sm truncate">
                      {conv.title || 'Untitled conversation'}
                    </span>
                    <button
                      onClick={(e) => handleDelete(e, conv.id)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-300 dark:hover:bg-gray-600 rounded transition-all"
                      title="Delete conversation"
                    >
                      {deletingId === conv.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-gray-500 dark:text-gray-400" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400 hover:text-red-500 dark:hover:text-red-400" />
                      )}
                    </button>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onToggle}
        />
      )}
    </>
  )
}
