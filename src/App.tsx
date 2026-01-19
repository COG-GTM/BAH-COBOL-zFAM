import { useState, useEffect } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  Shield, 
  Code, 
  FileText, 
  Database, 
  Lock, 
  Zap, 
  Target, 
  CheckCircle,
  ArrowRight,
  ExternalLink,
  Server,
  Layers,
  GitBranch,
  BarChart3,
  Users,
  TrendingUp,
  BookOpen,
  ArrowLeft
} from 'lucide-react'
import './App.css'

// Access code for the demo
const ACCESS_CODE = '8421'

// US Flag SVG (black/white minimalist)
const USFlag = () => (
  <svg width="24" height="16" viewBox="0 0 24 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="24" height="16" fill="#fafafa"/>
    <rect width="10" height="8" fill="#27272a"/>
    <g fill="#fafafa">
      <circle cx="1.5" cy="1" r="0.4"/>
      <circle cx="3.5" cy="1" r="0.4"/>
      <circle cx="5.5" cy="1" r="0.4"/>
      <circle cx="7.5" cy="1" r="0.4"/>
      <circle cx="2.5" cy="2" r="0.4"/>
      <circle cx="4.5" cy="2" r="0.4"/>
      <circle cx="6.5" cy="2" r="0.4"/>
      <circle cx="1.5" cy="3" r="0.4"/>
      <circle cx="3.5" cy="3" r="0.4"/>
      <circle cx="5.5" cy="3" r="0.4"/>
      <circle cx="7.5" cy="3" r="0.4"/>
      <circle cx="2.5" cy="4" r="0.4"/>
      <circle cx="4.5" cy="4" r="0.4"/>
      <circle cx="6.5" cy="4" r="0.4"/>
      <circle cx="1.5" cy="5" r="0.4"/>
      <circle cx="3.5" cy="5" r="0.4"/>
      <circle cx="5.5" cy="5" r="0.4"/>
      <circle cx="7.5" cy="5" r="0.4"/>
      <circle cx="2.5" cy="6" r="0.4"/>
      <circle cx="4.5" cy="6" r="0.4"/>
      <circle cx="6.5" cy="6" r="0.4"/>
    </g>
    <g fill="#27272a">
      <rect y="1.2" width="24" height="1.2" x="10"/>
      <rect y="3.6" width="24" height="1.2" x="10"/>
      <rect y="6" width="24" height="1.2" x="10"/>
      <rect y="8.4" width="24" height="1.2"/>
      <rect y="10.8" width="24" height="1.2"/>
      <rect y="13.2" width="24" height="1.2"/>
    </g>
  </svg>
)

// Cognition Sprocket Logo
const CognitionSprocket = () => (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M16 4L18 10H24L19 14L21 20L16 16L11 20L13 14L8 10H14L16 4Z" fill="#3969CA"/>
    <circle cx="16" cy="16" r="4" fill="#21C19A"/>
  </svg>
)

// Access Code Screen Component
const AccessCodeScreen = ({ onSuccess }: { onSuccess: () => void }) => {
  const [code, setCode] = useState('')
  const [error, setError] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (code === ACCESS_CODE) {
      onSuccess()
    } else {
      setError(true)
      setCode('')
      setTimeout(() => setError(false), 2000)
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center grid-pattern">
      <div className="hero-glow absolute inset-0 pointer-events-none" />
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 text-center"
      >
        <div className="flex items-center justify-center gap-3 mb-8">
          <CognitionSprocket />
          <span className="text-[#71717a] text-sm tracking-widest uppercase">By Cognition</span>
        </div>
        <h1 className="text-4xl font-bold text-[#fafafa] mb-4">COBOL Modernization Demo</h1>
        <p className="text-[#71717a] mb-8">Enter access code to continue</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            maxLength={4}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            className={`access-code-input w-48 bg-[#18181b] border ${error ? 'border-red-500' : 'border-[#27272a]'} rounded-lg py-4 text-[#fafafa] focus:outline-none focus:border-[#3969CA]`}
            placeholder="----"
            autoFocus
          />
          {error && <p className="text-red-500 text-sm">Invalid access code</p>}
          <div>
            <button
              type="submit"
              className="bg-[#fafafa] text-[#0a0a0f] px-8 py-3 rounded-full font-medium hover:bg-[#e4e4e7] transition-colors"
            >
              Enter Demo
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

// Government Banner Component
const GovBanner = () => (
  <div className="bg-[#18181b] border-b border-[#27272a] py-2">
    <div className="max-w-7xl mx-auto px-6 flex items-center gap-3">
      <USFlag />
      <span className="text-[#71717a] text-xs tracking-wider uppercase">
        An Official Demo for US Federal Agencies
      </span>
    </div>
  </div>
)

// Header Component
const Header = () => (
  <header className="sticky top-0 z-50 bg-[#0a0a0f]/90 backdrop-blur-md border-b border-[#27272a]">
    <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <CognitionSprocket />
        <div>
          <span className="text-[#fafafa] font-semibold">COBOL Modernization</span>
          <span className="text-[#71717a] text-sm ml-2">by Cognition</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <a 
          href="https://windsurf.com/enterprise/government" 
          target="_blank" 
          rel="noopener noreferrer"
          className="text-[#71717a] text-sm hover:text-[#fafafa] transition-colors flex items-center gap-1"
        >
          FedRAMP Info <ExternalLink size={14} />
        </a>
        <a 
          href="https://cognition.ai" 
          target="_blank" 
          rel="noopener noreferrer"
          className="bg-[#fafafa] text-[#0a0a0f] px-6 py-2 rounded-full text-sm font-medium hover:bg-[#e4e4e7] transition-colors"
        >
          Get Started
        </a>
      </div>
    </div>
  </header>
)

// Hero Section
const HeroSection = () => (
  <section className="relative section-spacing overflow-hidden">
    <div className="hero-glow absolute inset-0 pointer-events-none" />
    <div className="sprocket-pattern absolute left-0 top-0 w-72 h-full opacity-20" />
    <div className="sprocket-pattern absolute right-0 top-0 w-72 h-full opacity-20" />
    
    <div className="max-w-7xl mx-auto px-6 relative z-10">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="text-center mb-16"
      >
        <p className="text-[#3969CA] text-sm tracking-widest uppercase mb-4">Powered by Cognition AI</p>
        <h1 className="text-5xl md:text-6xl font-bold text-[#fafafa] mb-6 leading-tight">
          COBOL Modernization<br />
          <span className="gradient-text">with Devin AI</span>
        </h1>
        <p className="text-xl text-[#71717a] max-w-3xl mx-auto mb-6">
          Accelerating Legacy System Transformation for Federal Agencies
        </p>
        <Link 
          to="/whitepaper"
          className="inline-flex items-center gap-2 text-[#3969CA] hover:text-[#21C19A] transition-colors"
        >
          <BookOpen className="w-5 h-5" />
          Read the Executive Whitepaper
          <ArrowRight className="w-4 h-4" />
        </Link>
      </motion.div>

      {/* Key Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-16"
      >
        {[
          { value: '80%', label: 'Effort Savings', icon: TrendingUp },
          { value: '90%', label: 'Functionality Migrated', icon: CheckCircle },
          { value: '100%', label: 'Documentation Coverage', icon: FileText }
        ].map((metric, i) => (
          <div key={i} className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 text-center card-hover">
            <metric.icon className="w-8 h-8 text-[#3969CA] mx-auto mb-3" />
            <div className="text-4xl font-bold gradient-text mb-2">{metric.value}</div>
            <div className="text-[#71717a]">{metric.label}</div>
          </div>
        ))}
      </motion.div>

      {/* Info Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, delay: 0.3 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
      >
        <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
          <h3 className="text-[#71717a] text-sm uppercase tracking-wider mb-2">Mission</h3>
          <p className="text-[#fafafa]">Modernize federal COBOL systems with AI-powered analysis, documentation, and migration support</p>
        </div>
        <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
          <h3 className="text-[#71717a] text-sm uppercase tracking-wider mb-2">Built By</h3>
          <p className="text-[#fafafa]">Cognition AI</p>
        </div>
        <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
          <h3 className="text-[#71717a] text-sm uppercase tracking-wider mb-2">Status</h3>
          <p className="text-[#21C19A]">Production Ready</p>
        </div>
      </motion.div>
    </div>
  </section>
)

// Value Proposition Section
const ValuePropositionSection = () => (
  <section className="section-spacing bg-[#18181b]/50">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Why Modernize COBOL Now</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          Federal mandates and workforce challenges demand immediate action on legacy system modernization
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 card-hover"
        >
          <Target className="w-10 h-10 text-[#3969CA] mb-4" />
          <h3 className="text-xl font-semibold text-[#fafafa] mb-3">Executive Mandate</h3>
          <p className="text-[#71717a] mb-4">
            The War Department AI Acceleration Strategy mandates modernization of legacy systems to secure American military AI advantage.
          </p>
          <a 
            href="https://www.war.gov/News/Releases/Release/Article/4376420/war-department-launches-ai-acceleration-strategy-to-secure-american-military-ai/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#3969CA] text-sm flex items-center gap-1 hover:underline"
          >
            Read the Strategy <ExternalLink size={14} />
          </a>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 card-hover"
        >
          <Zap className="w-10 h-10 text-[#21C19A] mb-4" />
          <h3 className="text-xl font-semibold text-[#fafafa] mb-3">Devin's Unique Capabilities</h3>
          <p className="text-[#71717a]">
            Devin provides deep comprehension of complex COBOL programs, automated documentation generation, and strategic modernization planning that no other tool can match.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 card-hover"
        >
          <Users className="w-10 h-10 text-[#0294DE] mb-4" />
          <h3 className="text-xl font-semibold text-[#fafafa] mb-3">Talent Enablement</h3>
          <p className="text-[#71717a]">
            Address mainframe skills scarcity by enabling developers without deep COBOL experience to contribute effectively through AI-powered documentation and guidance.
          </p>
        </motion.div>
      </div>
    </div>
  </section>
)

// Migration Approach Section
const MigrationApproachSection = () => (
  <section className="section-spacing">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <p className="text-[#3969CA] text-sm tracking-widest uppercase mb-2">Proven with World's Largest SI</p>
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Migration Approach</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          A phased approach to transform monolithic COBOL systems into modern microservices architecture
        </p>
      </motion.div>

      {/* Architecture Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 mb-12"
      >
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="text-center">
            <div className="bg-[#27272a] rounded-lg p-6 mb-3">
              <Server className="w-12 h-12 text-[#71717a] mx-auto" />
            </div>
            <h4 className="text-[#fafafa] font-medium">Monolithic COBOL</h4>
            <p className="text-[#71717a] text-sm">~4K LOC, ~20 files</p>
            <p className="text-[#71717a] text-sm">7 copybooks, 5 DCLGEN</p>
            <p className="text-[#71717a] text-sm">4 CICS, 4 BMS</p>
          </div>
          
          <div className="flex items-center">
            <ArrowRight className="w-8 h-8 text-[#3969CA]" />
          </div>
          
          <div className="text-center flex-1">
            <div className="bg-gradient-to-r from-[#3969CA]/20 to-[#21C19A]/20 rounded-lg p-6 mb-3 border border-[#3969CA]/30">
              <Layers className="w-12 h-12 text-[#3969CA] mx-auto" />
            </div>
            <h4 className="text-[#fafafa] font-medium">Devin Analysis</h4>
            <p className="text-[#71717a] text-sm">Reverse Engineering</p>
            <p className="text-[#71717a] text-sm">Business Rules Extraction</p>
            <p className="text-[#71717a] text-sm">Entity & User Story Generation</p>
          </div>
          
          <div className="flex items-center">
            <ArrowRight className="w-8 h-8 text-[#21C19A]" />
          </div>
          
          <div className="text-center">
            <div className="bg-[#21C19A]/20 rounded-lg p-6 mb-3 border border-[#21C19A]/30">
              <GitBranch className="w-12 h-12 text-[#21C19A] mx-auto" />
            </div>
            <h4 className="text-[#fafafa] font-medium">Modern 3-Tier</h4>
            <p className="text-[#71717a] text-sm">React Frontend</p>
            <p className="text-[#71717a] text-sm">Python/Flask Backend</p>
            <p className="text-[#71717a] text-sm">PostgreSQL Database</p>
          </div>
        </div>
      </motion.div>

      {/* Phases */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-[#3969CA]/20 rounded-full p-2">
              <Code className="w-6 h-6 text-[#3969CA]" />
            </div>
            <h3 className="text-xl font-semibold text-[#fafafa]">Phase 1: Reverse Engineering</h3>
          </div>
          <ul className="space-y-3 text-[#71717a]">
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Extract business rules from COBOL procedures
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Identify entities and data relationships
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Generate user stories from program logic
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Document CICS transaction patterns
            </li>
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-[#21C19A]/20 rounded-full p-2">
              <Layers className="w-6 h-6 text-[#21C19A]" />
            </div>
            <h3 className="text-xl font-semibold text-[#fafafa]">Phase 2: Forward Engineering</h3>
          </div>
          <ul className="space-y-3 text-[#71717a]">
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Generate microservices architecture
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Create React frontend components
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Design modern database schema
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
              Implement API layer with documentation
            </li>
          </ul>
        </motion.div>
      </div>
    </div>
  </section>
)

// Case Studies Section
const CaseStudiesSection = () => (
  <section className="section-spacing bg-[#18181b]/50">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Proven Results</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          Devin has successfully modernized COBOL systems across financial services, healthcare, and government sectors
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-6 h-6 text-[#3969CA]" />
            <span className="text-[#71717a] text-sm">Financial Services</span>
          </div>
          <h3 className="text-lg font-semibold text-[#fafafa] mb-3">Global Tier 1 Bank</h3>
          <ul className="space-y-2 text-[#71717a] text-sm mb-4">
            <li>500+ Devin sessions completed</li>
            <li>Field-level data migrations</li>
            <li>Automated validation testing</li>
            <li>Iterative playbook evolution</li>
          </ul>
          <div className="flex items-center gap-2 text-[#21C19A] text-sm">
            <CheckCircle className="w-4 h-4" />
            Production deployed
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-6 h-6 text-[#21C19A]" />
            <span className="text-[#71717a] text-sm">Financial Services</span>
          </div>
          <h3 className="text-lg font-semibold text-[#fafafa] mb-3">Fortune 500 Insurance</h3>
          <ul className="space-y-2 text-[#71717a] text-sm mb-4">
            <li>Batch/CICS migrations</li>
            <li>File transfer modernization</li>
            <li>Automated compilation feedback</li>
            <li>Cross-system validation</li>
          </ul>
          <div className="flex items-center gap-2 text-[#21C19A] text-sm">
            <CheckCircle className="w-4 h-4" />
            In production
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-6 h-6 text-[#0294DE]" />
            <span className="text-[#71717a] text-sm">Healthcare</span>
          </div>
          <h3 className="text-lg font-semibold text-[#fafafa] mb-3">Fortune 100 Healthcare</h3>
          <ul className="space-y-2 text-[#71717a] text-sm mb-4">
            <li>Repository integration complete</li>
            <li>70-80% completion rate</li>
            <li>Repetitive changes automated</li>
            <li>Cross-component consistency</li>
          </ul>
          <div className="flex items-center gap-2 text-[#21C19A] text-sm">
            <CheckCircle className="w-4 h-4" />
            Scaling deployment
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-6 h-6 text-[#3969CA]" />
            <span className="text-[#71717a] text-sm">Federal Agency</span>
          </div>
          <h3 className="text-lg font-semibold text-[#fafafa] mb-3">Defense Contractor</h3>
          <ul className="space-y-2 text-[#71717a] text-sm mb-4">
            <li>Legacy system documentation</li>
            <li>STIG compliance analysis</li>
            <li>Security pattern extraction</li>
            <li>Modernization roadmap</li>
          </ul>
          <div className="flex items-center gap-2 text-[#21C19A] text-sm">
            <CheckCircle className="w-4 h-4" />
            Assessment complete
          </div>
        </motion.div>
      </div>
    </div>
  </section>
)

// Technical Capabilities Section
const TechnicalCapabilitiesSection = () => (
  <section className="section-spacing">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Technical Capabilities</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          Deep understanding of mainframe patterns and enterprise COBOL architectures
        </p>
      </motion.div>

      <Tabs defaultValue="analysis" className="w-full">
        <TabsList className="grid w-full grid-cols-3 bg-[#18181b] border border-[#27272a] rounded-lg p-1 mb-8">
          <TabsTrigger value="analysis" className="data-[state=active]:bg-[#3969CA] data-[state=active]:text-white rounded-md">
            Code Analysis
          </TabsTrigger>
          <TabsTrigger value="patterns" className="data-[state=active]:bg-[#3969CA] data-[state=active]:text-white rounded-md">
            COBOL Patterns
          </TabsTrigger>
          <TabsTrigger value="integration" className="data-[state=active]:bg-[#3969CA] data-[state=active]:text-white rounded-md">
            Integration
          </TabsTrigger>
        </TabsList>

        <TabsContent value="analysis" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <FileText className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Automated Documentation</h4>
              <p className="text-[#71717a] text-sm">
                Transform dense COBOL procedures into clear, navigable documentation. Analyze complex programs (4,000+ lines) and generate comprehensive API documentation with business rule extraction.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Layers className="w-8 h-8 text-[#21C19A] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Architecture Mapping</h4>
              <p className="text-[#71717a] text-sm">
                Visualize relationships between system components including multi-tier <span className="text-[#fafafa]">VSAM</span> <span className="text-[#71717a] text-xs">(file storage)</span> architectures, program dispatch models, and security integration patterns.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Database className="w-8 h-8 text-[#0294DE] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Data Flow Analysis</h4>
              <p className="text-[#71717a] text-sm">
                Trace data movement across copybooks, working storage, and file definitions. Map <span className="text-[#fafafa]">DCLGEN</span> <span className="text-[#71717a] text-xs">(DB2 declarations)</span> structures to database schemas and identify data transformation points.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Code className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Business Rule Extraction</h4>
              <p className="text-[#71717a] text-sm">
                Identify and document embedded business logic, validation rules, and calculation algorithms from procedural code into structured specifications.
              </p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="patterns" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Server className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">CICS Transaction Handling</h4>
              <p className="text-[#71717a] text-sm mb-3">
                Deep analysis of <span className="text-[#fafafa]">CICS</span> <span className="text-[#71717a] text-xs">(transaction processor)</span> patterns: EXEC CICS commands, <span className="text-[#fafafa]">XCTL/LINK</span> <span className="text-[#71717a] text-xs">(program transfers)</span>, <span className="text-[#fafafa]">COMMAREA</span> <span className="text-[#71717a] text-xs">(data passing)</span> parameter passing, HANDLE CONDITION/ABEND error management, and <span className="text-[#fafafa]">BMS</span> <span className="text-[#71717a] text-xs">(screen maps)</span> processing.
              </p>
              <code className="text-xs text-[#71717a] bg-[#27272a] px-2 py-1 rounded">TXNRTR001.cbl, TXNPROC002.cbl</code>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Database className="w-8 h-8 text-[#21C19A] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">VSAM & DB2 Operations</h4>
              <p className="text-[#71717a] text-sm mb-3">
                <span className="text-[#fafafa]">VSAM</span> <span className="text-[#71717a] text-xs">(file storage)</span> browse operations (STARTBR, READNEXT, READPREV), <span className="text-[#fafafa]">KSDS/ESDS/RRDS</span> <span className="text-[#71717a] text-xs">(file types)</span> handling, embedded SQL parsing, <span className="text-[#fafafa]">DCLGEN</span> <span className="text-[#71717a] text-xs">(DB2 declarations)</span> structure mapping, and cursor management patterns.
              </p>
              <code className="text-xs text-[#71717a] bg-[#27272a] px-2 py-1 rounded">FILEHNDL003.cbl, DBACCESS004.cbl</code>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Code className="w-8 h-8 text-[#0294DE] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Copybook & Linkage Analysis</h4>
              <p className="text-[#71717a] text-sm mb-3">
                Parse <span className="text-[#fafafa]">COPY</span> <span className="text-[#71717a] text-xs">(include files)</span> statements, resolve nested copybook hierarchies, analyze <span className="text-[#fafafa]">LINKAGE SECTION</span> <span className="text-[#71717a] text-xs">(parameter definitions)</span>, and map data structures across program boundaries.
              </p>
              <code className="text-xs text-[#71717a] bg-[#27272a] px-2 py-1 rounded">CPYBOOK001.cpy, LINKAGE002.cpy</code>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Lock className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Security & Authorization</h4>
              <p className="text-[#71717a] text-sm mb-3">
                <span className="text-[#fafafa]">RACF</span> <span className="text-[#71717a] text-xs">(access control)</span> integration patterns, field-level authorization, <span className="text-[#fafafa]">SAF</span> <span className="text-[#71717a] text-xs">(security interface)</span> calls, and security exit analysis for federal compliance requirements.
              </p>
              <code className="text-xs text-[#71717a] bg-[#27272a] px-2 py-1 rounded">SECAUTH001.cbl, RACFINTF002.cbl</code>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="integration" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <GitBranch className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">API Generation & Modernization</h4>
              <p className="text-[#71717a] text-sm">
                Generate RESTful APIs from COBOL programs, map <span className="text-[#fafafa]">COMMAREA</span> <span className="text-[#71717a] text-xs">(data passing)</span> structures to JSON schemas, create OpenAPI specifications, and implement modern authentication patterns.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Zap className="w-8 h-8 text-[#21C19A] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Code Generation</h4>
              <p className="text-[#71717a] text-sm">
                Generate equivalent Python/Java/TypeScript code from COBOL business logic, create database migration scripts from <span className="text-[#fafafa]">DCLGEN</span> <span className="text-[#71717a] text-xs">(DB2 declarations)</span>, and produce microservices from monolithic programs.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <Layers className="w-8 h-8 text-[#0294DE] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Batch to Event-Driven</h4>
              <p className="text-[#71717a] text-sm">
                Transform <span className="text-[#fafafa]">JCL</span> <span className="text-[#71717a] text-xs">(job control)</span> batch workflows into event-driven architectures, convert sequential file processing to streaming patterns, and modernize scheduling dependencies.
              </p>
            </div>
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-6">
              <FileText className="w-8 h-8 text-[#3969CA] mb-4" />
              <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Test Generation</h4>
              <p className="text-[#71717a] text-sm">
                Generate unit tests from existing COBOL test cases, create integration test suites, and produce validation scripts to ensure functional equivalence post-migration.
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  </section>
)

// Engagement Approach Section
const EngagementApproachSection = () => (
  <section className="section-spacing bg-[#18181b]/50">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Engagement Approach</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          A structured methodology for successful COBOL modernization
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="relative"
        >
          <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 h-full">
            <div className="absolute -top-4 left-8 bg-[#3969CA] text-white text-sm font-bold px-4 py-1 rounded-full">
              Phase 1
            </div>
            <h3 className="text-xl font-semibold text-[#fafafa] mt-4 mb-4">Assessment & Analysis</h3>
            <ul className="space-y-3 text-[#71717a]">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Codebase inventory and cataloging
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Pattern documentation
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Integration mapping
              </li>
            </ul>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="relative"
        >
          <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 h-full">
            <div className="absolute -top-4 left-8 bg-[#21C19A] text-white text-sm font-bold px-4 py-1 rounded-full">
              Phase 2
            </div>
            <h3 className="text-xl font-semibold text-[#fafafa] mt-4 mb-4">Strategy Development</h3>
            <ul className="space-y-3 text-[#71717a]">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Modernization roadmap
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                API design specifications
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Data migration strategy
              </li>
            </ul>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="relative"
        >
          <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 h-full">
            <div className="absolute -top-4 left-8 bg-[#0294DE] text-white text-sm font-bold px-4 py-1 rounded-full">
              Phase 3
            </div>
            <h3 className="text-xl font-semibold text-[#fafafa] mt-4 mb-4">Implementation Support</h3>
            <ul className="space-y-3 text-[#71717a]">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Code generation assistance
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Testing guidance
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-5 h-5 text-[#21C19A] mt-0.5 flex-shrink-0" />
                Documentation automation
              </li>
            </ul>
          </div>
        </motion.div>
      </div>

      {/* Implementation Roadmap */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
      >
        <h3 className="text-xl font-semibold text-[#fafafa] mb-6 text-center">Implementation Roadmap</h3>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex-1 text-center">
            <div className="bg-[#3969CA]/20 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-3">
              <Target className="w-8 h-8 text-[#3969CA]" />
            </div>
            <h4 className="text-[#fafafa] font-medium mb-1">Pilot</h4>
            <p className="text-[#71717a] text-sm">Specific repos, validation</p>
          </div>
          <ArrowRight className="w-6 h-6 text-[#27272a] hidden md:block" />
          <div className="flex-1 text-center">
            <div className="bg-[#21C19A]/20 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-3">
              <TrendingUp className="w-8 h-8 text-[#21C19A]" />
            </div>
            <h4 className="text-[#fafafa] font-medium mb-1">Rollout</h4>
            <p className="text-[#71717a] text-sm">Agency-wide deployment</p>
          </div>
          <ArrowRight className="w-6 h-6 text-[#27272a] hidden md:block" />
          <div className="flex-1 text-center">
            <div className="bg-[#0294DE]/20 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-3">
              <Shield className="w-8 h-8 text-[#0294DE]" />
            </div>
            <h4 className="text-[#fafafa] font-medium mb-1">Governance</h4>
            <p className="text-[#71717a] text-sm">Long-term maintenance</p>
          </div>
        </div>
      </motion.div>
    </div>
  </section>
)

// Success Metrics Section
const SuccessMetricsSection = () => (
  <section className="section-spacing">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Success Metrics</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          Measurable outcomes that demonstrate modernization value
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-6">
            <BarChart3 className="w-8 h-8 text-[#3969CA]" />
            <h3 className="text-xl font-semibold text-[#fafafa]">Technical Indicators</h3>
          </div>
          <ul className="space-y-4">
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Reduced Complexity</span>
              <span className="text-[#21C19A] font-medium">Clearer structure</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Improved Maintainability</span>
              <span className="text-[#21C19A] font-medium">Better documentation</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Enhanced Integration</span>
              <span className="text-[#21C19A] font-medium">Modern APIs</span>
            </li>
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-8 h-8 text-[#21C19A]" />
            <h3 className="text-xl font-semibold text-[#fafafa]">Business Value</h3>
          </div>
          <ul className="space-y-4">
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Effort Savings</span>
              <span className="text-[#21C19A] font-medium">80%</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Functionality Migrated</span>
              <span className="text-[#21C19A] font-medium">~90%</span>
            </li>
            <li className="flex items-center justify-between">
              <span className="text-[#71717a]">Risk Reduction</span>
              <span className="text-[#21C19A] font-medium">Comprehensive docs</span>
            </li>
          </ul>
        </motion.div>
      </div>
    </div>
  </section>
)

// STIG & NIST Compliance Section
const ComplianceSection = () => (
  <section className="section-spacing bg-[#18181b]/50">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-4">Federal Security Compliance</h2>
        <p className="text-[#71717a] max-w-2xl mx-auto">
          Built-in support for STIG and NIST 800-53 security standards
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <Shield className="w-8 h-8 text-[#3969CA] mb-4" />
          <h4 className="text-lg font-semibold text-[#fafafa] mb-2">STIG Compliance</h4>
          <p className="text-[#71717a] text-sm">V-220629, V-220631, V-220633 controls automated</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <Lock className="w-8 h-8 text-[#21C19A] mb-4" />
          <h4 className="text-lg font-semibold text-[#fafafa] mb-2">NIST 800-53</h4>
          <p className="text-[#71717a] text-sm">AC, AU, IA, SC, SI control families supported</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <CheckCircle className="w-8 h-8 text-[#0294DE] mb-4" />
          <h4 className="text-lg font-semibold text-[#fafafa] mb-2">FedRAMP Alignment</h4>
          <p className="text-[#71717a] text-sm">Cloud security controls for federal systems</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.4 }}
          className="bg-[#18181b] border border-[#27272a] rounded-xl p-6 card-hover"
        >
          <Zap className="w-8 h-8 text-[#3969CA] mb-4" />
          <h4 className="text-lg font-semibold text-[#fafafa] mb-2">Automated Scanning</h4>
          <p className="text-[#71717a] text-sm">SonarQube integration for continuous compliance</p>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center"
      >
        <a 
          href="https://github.com/COG-GTM/fedreral_security_comliance"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-[#3969CA] hover:underline"
        >
          View Federal Security Compliance Framework <ExternalLink size={16} />
        </a>
      </motion.div>
    </div>
  </section>
)

// Cognition Platform Section
const CognitionPlatformSection = () => (
  <section className="section-spacing">
    <div className="max-w-7xl mx-auto px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <h2 className="text-3xl font-bold text-[#fafafa] mb-2">Cognition AI Platform</h2>
        <p className="text-[#71717a]">The world's first AI software engineer + agentic IDE</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-gradient-to-br from-[#3969CA]/20 to-[#3969CA]/5 border border-[#3969CA]/30 rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-[#3969CA] rounded-lg p-2">
              <Code className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-[#fafafa]">Devin</h3>
          </div>
          <p className="text-[#71717a] mb-4">
            The world's first AI software engineer. Devin can plan, code, debug, and deploy complex software projects autonomously.
          </p>
          <ul className="space-y-2 text-[#71717a]">
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Deep COBOL comprehension
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Automated documentation
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Migration planning
            </li>
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          className="bg-gradient-to-br from-[#21C19A]/20 to-[#21C19A]/5 border border-[#21C19A]/30 rounded-xl p-8"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-[#21C19A] rounded-lg p-2">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-[#fafafa]">Windsurf</h3>
          </div>
          <p className="text-[#71717a] mb-4">
            AI-powered IDE that supercharges developer productivity with intelligent code completion and real-time assistance.
          </p>
          <ul className="space-y-2 text-[#71717a]">
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Context-aware suggestions
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Multi-file editing
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-[#21C19A]" />
              Integrated debugging
            </li>
          </ul>
        </motion.div>
      </div>

      {/* Workflow Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="bg-[#18181b] border border-[#27272a] rounded-xl p-8"
      >
        <h3 className="text-xl font-semibold text-[#fafafa] mb-6 text-center">Modernization Workflow</h3>
        <div className="flex flex-wrap items-center justify-center gap-4">
          {['Assess', 'Plan', 'Build', 'Validate', 'Deploy'].map((step, i) => (
            <div key={step} className="flex items-center gap-4">
              <div className="bg-[#27272a] rounded-lg px-6 py-3 text-[#fafafa] font-medium">
                {step}
              </div>
              {i < 4 && <ArrowRight className="w-5 h-5 text-[#3969CA]" />}
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  </section>
)

// Call to Action Section
const CTASection = () => (
  <section className="section-spacing">
    <div className="max-w-4xl mx-auto px-6 text-center">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
      >
        <h2 className="text-4xl font-bold text-[#fafafa] mb-6">
          Ready to Modernize Your COBOL Systems?
        </h2>
        <p className="text-xl text-[#71717a] mb-8">
          Join leading federal agencies in transforming legacy systems with AI-powered development. 
          Devin and Windsurf are ready to accelerate your modernization journey.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <a 
            href="https://cognition.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-[#fafafa] text-[#0a0a0f] px-8 py-3 rounded-full font-medium hover:bg-[#e4e4e7] transition-colors"
          >
            Schedule Briefing
          </a>
          <a 
            href="https://github.com/COG-GTM/BAH-COBOL-zFAM"
            target="_blank"
            rel="noopener noreferrer"
            className="border border-[#27272a] text-[#fafafa] px-8 py-3 rounded-full font-medium hover:border-[#3969CA] transition-colors"
          >
            View the Code
          </a>
          <a 
            href="https://cognition.ai"
            target="_blank"
            rel="noopener noreferrer"
            className="border border-[#27272a] text-[#fafafa] px-8 py-3 rounded-full font-medium hover:border-[#21C19A] transition-colors"
          >
            Start Pilot
          </a>
        </div>
      </motion.div>
    </div>
  </section>
)

// Executive Whitepaper Page
const WhitepaperPage = () => {
  const navigate = useNavigate()
  
  return (
    <div className="min-h-screen bg-[#0a0a0f] grid-pattern">
      <div className="hero-glow absolute inset-0 pointer-events-none" />
      
      {/* Header */}
      <header className="sticky top-0 z-50 bg-[#0a0a0f]/95 backdrop-blur-sm border-b border-[#27272a]">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <button 
            onClick={() => navigate('/')}
            className="flex items-center gap-2 text-[#71717a] hover:text-[#fafafa] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Demo
          </button>
          <div className="flex items-center gap-3">
            <CognitionSprocket />
            <span className="text-[#71717a] text-sm">Executive Whitepaper</span>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="relative z-10 max-w-4xl mx-auto px-6 py-16">
        <motion.article
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="prose prose-invert max-w-none"
        >
          {/* Title */}
          <div className="text-center mb-16">
            <div className="flex items-center justify-center gap-2 mb-4">
              <BookOpen className="w-6 h-6 text-[#3969CA]" />
              <span className="text-[#3969CA] text-sm uppercase tracking-widest">Executive Whitepaper</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-[#fafafa] mb-6">
              COBOL Modernization with AI:<br />
              <span className="gradient-text">A New Paradigm</span>
            </h1>
            <p className="text-[#71717a] text-lg">
              How Cognition AI is solving the legacy modernization challenge that has eluded the industry for decades
            </p>
          </div>

          {/* Problem Statement */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-[#fafafa] mb-6 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#3969CA]/20 flex items-center justify-center">
                <span className="text-[#3969CA] font-bold">1</span>
              </div>
              The COBOL Challenge
            </h2>
            
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 mb-6">
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                COBOL remains the backbone of critical infrastructure across federal agencies, financial institutions, and healthcare organizations. An estimated 220 billion lines of COBOL code continue to process trillions of dollars in daily transactions, manage social security benefits, and power core banking systems. Yet this foundational technology faces an existential crisis that threatens operational continuity and national security.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                The challenge is multifaceted. First, there is a severe talent shortage: the average COBOL developer is approaching retirement age, and universities stopped teaching the language decades ago. Organizations report that finding qualified mainframe developers has become nearly impossible, with some positions remaining unfilled for years. Second, the accumulated technical debt is staggering. These systems have evolved over 40-60 years through countless modifications, often with minimal documentation. Business rules are embedded deep within procedural code, making it extremely difficult to understand what the system actually does versus what it was originally designed to do.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed">
                Perhaps most critically, the lack of codebase understanding creates a paralysis that prevents meaningful modernization. When no one fully comprehends how a system works, making structural changes becomes too risky. Organizations find themselves trapped: unable to modernize because they don't understand the code, and unable to understand the code because the people who wrote it are no longer available. This creates a vicious cycle where systems become increasingly brittle while the knowledge gap widens with each passing year.
              </p>
            </div>
          </section>

          {/* Our Approach */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-[#fafafa] mb-6 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#21C19A]/20 flex items-center justify-center">
                <span className="text-[#21C19A] font-bold">2</span>
              </div>
              The Cognition Approach
            </h2>
            
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 mb-6">
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                Cognition AI has developed a fundamentally different approach to COBOL modernization, one that addresses the root cause of the problem rather than just its symptoms. Our methodology begins with comprehensive understanding before any code transformation occurs. This is where traditional approaches have failed: they attempt to translate code without first understanding what it does, leading to modernization projects that either fail outright or produce systems that don't accurately replicate the original business logic.
              </p>
              
              <h3 className="text-xl font-semibold text-[#fafafa] mt-8 mb-4">DeepWiki: Architecture Visualization & Understanding</h3>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                Our foundation is DeepWiki, an AI-powered system that creates comprehensive, navigable documentation from existing COBOL codebases. DeepWiki doesn't just parse syntax; it understands semantics. It traces data flows across copybooks and program boundaries, identifies business rules embedded in conditional logic, maps relationships between CICS transactions and VSAM files, and documents the implicit knowledge that exists only in the code itself. The result is a living knowledge base that makes decades of accumulated complexity accessible and understandable.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                DeepWiki analyzes program structures including WORKING-STORAGE definitions, LINKAGE SECTION parameters, and FILE-CONTROL entries. It understands CICS patterns like EXEC CICS commands, COMMAREA data passing, and BMS screen maps. It parses embedded SQL, maps DCLGEN structures to database schemas, and traces the flow of data through complex batch processing chains defined in JCL. This comprehensive analysis creates the foundation for informed modernization decisions.
              </p>

              <h3 className="text-xl font-semibold text-[#fafafa] mt-8 mb-4">Ask Devin: Strategic Planning & Architecture</h3>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                With understanding established, Ask Devin enables strategic planning for modernization. Teams can query the codebase in natural language: "What business rules govern account validation?" or "Which programs would be affected if we change the customer record format?" Ask Devin provides accurate, contextual answers that would previously have required weeks of manual code review.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                More importantly, Ask Devin helps architects plan the modernization journey. It can identify logical service boundaries within monolithic programs, suggest microservices decomposition strategies, and highlight areas of high complexity that require special attention. It documents dependencies, identifies shared copybooks, and maps the integration points that must be preserved during migration. This planning capability transforms modernization from a risky leap of faith into a methodical, well-understood process.
              </p>

              <h3 className="text-xl font-semibold text-[#fafafa] mt-8 mb-4">Devin Agent: Autonomous Code Generation & Testing</h3>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                The Devin agent represents the culmination of our approach: an AI software engineer capable of autonomous code generation, testing, and validation. Unlike simple code translation tools, Devin understands the intent behind COBOL code and generates idiomatic modern equivalents. It doesn't produce line-by-line translations that preserve COBOL's procedural structure in Python or Java; instead, it creates clean, maintainable code that follows modern best practices while preserving exact functional equivalence.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed">
                Devin handles the full spectrum of modernization tasks: generating RESTful APIs from CICS transactions, creating database migration scripts from DCLGEN definitions, transforming batch JCL workflows into event-driven architectures, and producing comprehensive test suites that validate functional equivalence. It can work autonomously on well-defined tasks or collaborate with human developers on complex transformations, always maintaining the context and understanding established through DeepWiki analysis.
              </p>
            </div>
          </section>

          {/* Why We've Won */}
          <section className="mb-16">
            <h2 className="text-2xl font-bold text-[#fafafa] mb-6 flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-[#0294DE]/20 flex items-center justify-center">
                <span className="text-[#0294DE] font-bold">3</span>
              </div>
              Why This Approach Succeeds
            </h2>
            
            <div className="bg-[#18181b] border border-[#27272a] rounded-xl p-8 mb-6">
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                The industry has attempted COBOL modernization for decades with limited success. Large-scale rewrite projects have failed spectacularly, automated translation tools have produced unmaintainable code, and gradual refactoring efforts have stalled due to complexity and risk. Cognition's approach succeeds where others have failed because it addresses the fundamental problem: understanding.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                Previous approaches treated modernization as primarily a translation problem. They assumed that if you could convert COBOL syntax to Java or Python syntax, the job was done. But syntax translation without semantic understanding produces code that is technically correct but practically useless: it preserves COBOL's 1960s-era programming patterns in a modern language, creating systems that are harder to maintain than the originals.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed mb-4">
                Our approach inverts this paradigm. We begin with deep understanding, then use that understanding to guide intelligent transformation. The AI doesn't just translate; it comprehends, plans, and generates. It understands that a particular PERFORM loop implements a business rule for interest calculation, and it generates a clean, well-documented function that implements that same rule in modern idioms. It recognizes that a complex CICS transaction can be decomposed into discrete microservices, and it generates the APIs, data contracts, and integration code to make that decomposition work.
              </p>
              <p className="text-[#a1a1aa] leading-relaxed">
                This is why Cognition has won major modernization initiatives at global financial institutions, Fortune 100 healthcare companies, and the world's largest system integrators. We've demonstrated 80% effort savings compared to traditional approaches, with 90% of functionality successfully migrated and 100% documentation coverage. Organizations that had been paralyzed by the complexity of their legacy systems are now making meaningful progress toward modernization, enabled by AI that finally makes their code understandable.
              </p>
            </div>
          </section>

          {/* Call to Action */}
          <section className="text-center">
            <div className="bg-gradient-to-r from-[#3969CA]/10 via-[#21C19A]/10 to-[#0294DE]/10 border border-[#27272a] rounded-xl p-12">
              <h2 className="text-2xl font-bold text-[#fafafa] mb-4">
                Ready to Modernize Your Legacy Systems?
              </h2>
              <p className="text-[#a1a1aa] mb-8 max-w-2xl mx-auto">
                Cognition AI is helping federal agencies and enterprises transform their COBOL systems with unprecedented speed and accuracy. Let us show you what's possible.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <a
                  href="https://cognition.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 bg-[#fafafa] text-[#0a0a0f] px-8 py-3 rounded-full font-semibold hover:bg-[#e4e4e7] transition-colors"
                >
                  Contact Cognition AI
                  <ArrowRight className="w-4 h-4" />
                </a>
                <button
                  onClick={() => navigate('/')}
                  className="inline-flex items-center gap-2 border border-[#27272a] text-[#fafafa] px-8 py-3 rounded-full font-semibold hover:bg-[#18181b] transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Demo
                </button>
              </div>
            </div>
          </section>
        </motion.article>
      </main>

      {/* Footer */}
      <footer className="relative z-10 bg-[#18181b] border-t border-[#27272a] mt-16">
        <div className="max-w-4xl mx-auto px-6 py-8 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <CognitionSprocket />
            <span className="text-[#71717a] text-sm">
              Cognition AI Platform - The world's first AI software engineer + agentic IDE
            </span>
          </div>
          <p className="text-[#71717a] text-sm">
            Built by Cognition AI - Devin, the world's first AI software engineer, and Windsurf
          </p>
        </div>
      </footer>
    </div>
  )
}

// Footer Component
const Footer = () => (
  <footer className="bg-[#18181b] border-t border-[#27272a]">
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <USFlag />
          <span className="text-[#71717a] text-sm">An Official Demo for US Federal Agencies</span>
        </div>
        <div className="flex items-center gap-3">
          <CognitionSprocket />
          <span className="text-[#71717a] text-sm">
            Cognition AI Platform - The world's first AI software engineer + agentic IDE
          </span>
        </div>
      </div>
      <div className="mt-6 pt-6 border-t border-[#27272a] text-center">
        <p className="text-[#71717a] text-sm">
          Built by Cognition AI - Devin, the world's first AI software engineer, and Windsurf
        </p>
      </div>
    </div>
  </footer>
)

// Main Demo Page Component
const MainPage = () => (
  <div className="min-h-screen bg-[#0a0a0f] grid-pattern">
    <GovBanner />
    <Header />
    <main>
      <HeroSection />
      <ValuePropositionSection />
      <MigrationApproachSection />
      <CaseStudiesSection />
      <TechnicalCapabilitiesSection />
      <EngagementApproachSection />
      <SuccessMetricsSection />
      <ComplianceSection />
      <CognitionPlatformSection />
      <CTASection />
    </main>
    <Footer />
  </div>
)

// Main App Component
function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  // Check for stored authentication
  useEffect(() => {
    const stored = sessionStorage.getItem('cobol-demo-auth')
    if (stored === 'true') {
      setIsAuthenticated(true)
    }
  }, [])

  const handleAccessSuccess = () => {
    sessionStorage.setItem('cobol-demo-auth', 'true')
    setIsAuthenticated(true)
  }

  if (!isAuthenticated) {
    return <AccessCodeScreen onSuccess={handleAccessSuccess} />
  }

  return (
    <Routes>
      <Route path="/" element={<MainPage />} />
      <Route path="/whitepaper" element={<WhitepaperPage />} />
    </Routes>
  )
}

export default App
