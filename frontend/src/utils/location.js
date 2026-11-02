/**
 * 智能节点地理位置与国家/区域解析器
 * 支持：国旗 Emoji、中文/英文地名正则匹配、Cloudflare Anycast CDN 识别、
 * 以及异步 IP/域名 GeoIP 归属地解析与多级缓存
 */

import { getFlagSvg } from './flags.js'

// 1. 常见国旗 Emoji 到国家信息的映射
export const EMOJI_FLAG_MAP = {
  '🇭🇰': { code: 'HK', flag: '🇭🇰', text: '香港' },
  '🇹🇼': { code: 'TW', flag: '🇹🇼', text: '台湾' },
  '🇯🇵': { code: 'JP', flag: '🇯🇵', text: '日本' },
  '🇸🇬': { code: 'SG', flag: '🇸🇬', text: '新加坡' },
  '🇺🇸': { code: 'US', flag: '🇺🇸', text: '美国' },
  '🇰🇷': { code: 'KR', flag: '🇰🇷', text: '韩国' },
  '🇬🇧': { code: 'GB', flag: '🇬🇧', text: '英国' },
  '🇩🇪': { code: 'DE', flag: '🇩🇪', text: '德国' },
  '🇫🇷': { code: 'FR', flag: '🇫🇷', text: '法国' },
  '🇨🇦': { code: 'CA', flag: '🇨🇦', text: '加拿大' },
  '🇦🇺': { code: 'AU', flag: '🇦🇺', text: '澳大利亚' },
  '🇷🇺': { code: 'RU', flag: '🇷🇺', text: '俄罗斯' },
  '🇮🇳': { code: 'IN', flag: '🇮🇳', text: '印度' },
  '🇹🇭': { code: 'TH', flag: '🇹🇭', text: '泰国' },
  '🇻🇳': { code: 'VN', flag: '🇻🇳', text: '越南' },
  '🇵🇭': { code: 'PH', flag: '🇵🇭', text: '菲律宾' },
  '🇲🇾': { code: 'MY', flag: '🇲🇾', text: '马来西亚' },
  '🇳🇱': { code: 'NL', flag: '🇳🇱', text: '荷兰' },
  '🇹🇷': { code: 'TR', flag: '🇹🇷', text: '土耳其' },
  '🇦🇷': { code: 'AR', flag: '🇦🇷', text: '阿根廷' },
  '🇧🇷': { code: 'BR', flag: '🇧🇷', text: '巴西' },
  '🇲🇽': { code: 'MX', flag: '🇲🇽', text: '墨西哥' },
  '🇮🇩': { code: 'ID', flag: '🇮🇩', text: '印尼' },
  '🇨🇭': { code: 'CH', flag: '🇨🇭', text: '瑞士' },
  '🇸🇪': { code: 'SE', flag: '🇸🇪', text: '瑞典' },
  '🇳🇴': { code: 'NO', flag: '🇳🇴', text: '挪威' },
  '🇫🇮': { code: 'FI', flag: '🇫🇮', text: '芬兰' },
  '🇮🇪': { code: 'IE', flag: '🇮🇪', text: '爱尔兰' },
  '🇮🇹': { code: 'IT', flag: '🇮🇹', text: '意大利' },
  '🇪🇸': { code: 'ES', flag: '🇪🇸', text: '西班牙' },
  '🇵🇹': { code: 'PT', flag: '🇵🇹', text: '葡萄牙' },
  '🇿🇦': { code: 'ZA', flag: '🇿🇦', text: '南非' },
  '🇦🇪': { code: 'AE', flag: '🇦🇪', text: '阿联酋' },
  '🇨🇳': { code: 'CN', flag: '🇨🇳', text: '中国' },
  '🇺🇲': { code: 'US', flag: '🇺🇸', text: '美国' }
}

// 2. 节点名称与地域代号精准规则列表
export const LOCATION_RULES = [
  // 香港
  {
    code: 'HK',
    flag: '🇭🇰',
    text: '香港',
    regex: /(?:^|[^a-zA-Z])(?:HK|HKG|Hong\s*Kong)(?:[^a-zA-Z]|$)|香港|深港|广港|沪港|京港/i
  },
  // 台湾
  {
    code: 'TW',
    flag: '🇹🇼',
    text: '台湾',
    regex: /(?:^|[^a-zA-Z])(?:TW|TWN|Taiwan|Taipei)(?:[^a-zA-Z]|$)|台湾|台北|台中|高雄|深台|广台|沪台/i
  },
  // 日本
  {
    code: 'JP',
    flag: '🇯🇵',
    text: '日本',
    regex: /(?:^|[^a-zA-Z])(?:JP|JPN|Japan|Tokyo|Osaka)(?:[^a-zA-Z]|$)|日本|东京|大阪|川崎|沪日|京日|广日|深日/i
  },
  // 新加坡
  {
    code: 'SG',
    flag: '🇸🇬',
    text: '新加坡',
    regex: /(?:^|[^a-zA-Z])(?:SG|SGP|Singapore)(?:[^a-zA-Z]|$)|新加坡|狮城|沪新|广新|深新|京新/i
  },
  // 美国
  {
    code: 'US',
    flag: '🇺🇸',
    text: '美国',
    regex: /(?:^|[^a-zA-Z])(?:US|USA|United\s*States|America|Los\s*Angeles|San\s*Jose|Seattle|Chicago|Dallas|New\s*York|Phoenix|Miami|Portland|Oregon|Virginia|Atlanta|Silicon\s*Valley)(?:[^a-zA-Z]|$)|美国|洛杉矶|硅谷|圣何塞|西雅图|芝加哥|达拉斯|纽约|波特兰|俄勒冈|凤凰城|弗吉尼亚|迈阿密|亚特兰大|沪美|中美|广美|深美|京美/i
  },
  // 韩国
  {
    code: 'KR',
    flag: '🇰🇷',
    text: '韩国',
    regex: /(?:^|[^a-zA-Z])(?:KR|KOR|Korea|Seoul)(?:[^a-zA-Z]|$)|韩国|首尔|仁川|沪韩|广韩|深韩/i
  },
  // 英国
  {
    code: 'GB',
    flag: '🇬🇧',
    text: '英国',
    regex: /(?:^|[^a-zA-Z])(?:UK|GB|GBR|United\s*Kingdom|Great\s*Britain|London)(?:[^a-zA-Z]|$)|英国|伦敦/i
  },
  // 德国
  {
    code: 'DE',
    flag: '🇩🇪',
    text: '德国',
    regex: /(?:^|[^a-zA-Z])(?:DE|DEU|Germany|Frankfurt|Berlin)(?:[^a-zA-Z]|$)|德国|法兰克福|柏林|京德/i
  },
  // 法国
  {
    code: 'FR',
    flag: '🇫🇷',
    text: '法国',
    regex: /(?:^|[^a-zA-Z])(?:FR|FRA|France|Paris)(?:[^a-zA-Z]|$)|法国|巴黎/i
  },
  // 加拿大
  {
    code: 'CA',
    flag: '🇨🇦',
    text: '加拿大',
    regex: /(?:^|[^a-zA-Z])(?:CA|CAN|Canada|Toronto|Vancouver)(?:[^a-zA-Z]|$)|加拿大|多伦多|温哥华/i
  },
  // 澳大利亚
  {
    code: 'AU',
    flag: '🇦🇺',
    text: '澳大利亚',
    regex: /(?:^|[^a-zA-Z])(?:AU|AUS|Australia|Sydney|Melbourne)(?:[^a-zA-Z]|$)|澳大利亚|澳洲|悉尼|墨尔本/i
  },
  // 俄罗斯
  {
    code: 'RU',
    flag: '🇷🇺',
    text: '俄罗斯',
    regex: /(?:^|[^a-zA-Z])(?:RU|RUS|Russia|Moscow)(?:[^a-zA-Z]|$)|俄罗斯|莫斯科|圣彼得堡/i
  },
  // 印度
  {
    code: 'IN',
    flag: '🇮🇳',
    text: '印度',
    regex: /(?:^|[^a-zA-Z])(?:IN|IND|India|Mumbai|Delhi)(?:[^a-zA-Z]|$)|印度|孟买|新德里/i
  },
  // 泰国
  {
    code: 'TH',
    flag: '🇹🇭',
    text: '泰国',
    regex: /(?:^|[^a-zA-Z])(?:TH|THA|Thailand|Bangkok)(?:[^a-zA-Z]|$)|泰国|曼谷/i
  },
  // 越南
  {
    code: 'VN',
    flag: '🇻🇳',
    text: '越南',
    regex: /(?:^|[^a-zA-Z])(?:VN|VNM|Vietnam|Hanoi|Ho\s*Chi\s*Minh)(?:[^a-zA-Z]|$)|越南|河内|胡志明/i
  },
  // 菲律宾
  {
    code: 'PH',
    flag: '🇵🇭',
    text: '菲律宾',
    regex: /(?:^|[^a-zA-Z])(?:PH|PHL|Philippines|Manila)(?:[^a-zA-Z]|$)|菲律宾|马尼拉/i
  },
  // 马来西亚
  {
    code: 'MY',
    flag: '🇲🇾',
    text: '马来西亚',
    regex: /(?:^|[^a-zA-Z])(?:MY|MYS|Malaysia|Kuala\s*Lumpur)(?:[^a-zA-Z]|$)|马来西亚|吉隆坡|大马|马来/i
  },
  // 荷兰
  {
    code: 'NL',
    flag: '🇳🇱',
    text: '荷兰',
    regex: /(?:^|[^a-zA-Z])(?:NL|NLD|Netherlands|Amsterdam)(?:[^a-zA-Z]|$)|荷兰|阿姆斯特丹/i
  },
  // 土耳其
  {
    code: 'TR',
    flag: '🇹🇷',
    text: '土耳其',
    regex: /(?:^|[^a-zA-Z])(?:TR|TUR|Turkey|Istanbul)(?:[^a-zA-Z]|$)|土耳其|伊斯坦布尔/i
  },
  // 阿根廷
  {
    code: 'AR',
    flag: '🇦🇷',
    text: '阿根廷',
    regex: /(?:^|[^a-zA-Z])(?:AR|ARG|Argentina)(?:[^a-zA-Z]|$)|阿根廷/i
  },
  // 巴西
  {
    code: 'BR',
    flag: '🇧🇷',
    text: '巴西',
    regex: /(?:^|[^a-zA-Z])(?:BR|BRA|Brazil|Sao\s*Paulo)(?:[^a-zA-Z]|$)|巴西|圣保罗/i
  },
  // 墨西哥
  {
    code: 'MX',
    flag: '🇲🇽',
    text: '墨西哥',
    regex: /(?:^|[^a-zA-Z])(?:MX|MEX|Mexico)(?:[^a-zA-Z]|$)|墨西哥/i
  },
  // 印尼
  {
    code: 'ID',
    flag: '🇮🇩',
    text: '印尼',
    regex: /(?:^|[^a-zA-Z])(?:ID|IDN|Indonesia|Jakarta)(?:[^a-zA-Z]|$)|印尼|印度尼西亚|雅加达/i
  },
  // 瑞士
  {
    code: 'CH',
    flag: '🇨🇭',
    text: '瑞士',
    regex: /(?:^|[^a-zA-Z])(?:CH|CHE|Switzerland|Zurich|Geneva)(?:[^a-zA-Z]|$)|瑞士|苏黎世|日内瓦/i
  },
  // 瑞典
  {
    code: 'SE',
    flag: '🇸🇪',
    text: '瑞典',
    regex: /(?:^|[^a-zA-Z])(?:SE|SWE|Sweden|Stockholm)(?:[^a-zA-Z]|$)|瑞典|斯德哥尔摩/i
  },
  // 挪威
  {
    code: 'NO',
    flag: '🇳🇴',
    text: '挪威',
    regex: /(?:^|[^a-zA-Z])(?:NO|NOR|Norway|Oslo)(?:[^a-zA-Z]|$)|挪威|奥斯陆/i
  },
  // 芬兰
  {
    code: 'FI',
    flag: '🇫🇮',
    text: '芬兰',
    regex: /(?:^|[^a-zA-Z])(?:FI|FIN|Finland|Helsinki)(?:[^a-zA-Z]|$)|芬兰|赫尔辛基/i
  },
  // 爱尔兰
  {
    code: 'IE',
    flag: '🇮🇪',
    text: '爱尔兰',
    regex: /(?:^|[^a-zA-Z])(?:IE|IRL|Ireland|Dublin)(?:[^a-zA-Z]|$)|爱尔兰|都柏林/i
  },
  // 意大利
  {
    code: 'IT',
    flag: '🇮🇹',
    text: '意大利',
    regex: /(?:^|[^a-zA-Z])(?:IT|ITA|Italy|Rome|Milan)(?:[^a-zA-Z]|$)|意大利|罗马|米兰/i
  },
  // 西班牙
  {
    code: 'ES',
    flag: '🇪🇸',
    text: '西班牙',
    regex: /(?:^|[^a-zA-Z])(?:ES|ESP|Spain|Madrid|Barcelona)(?:[^a-zA-Z]|$)|西班牙|马德里|巴塞罗那/i
  },
  // 葡萄牙
  {
    code: 'PT',
    flag: '🇵🇹',
    text: '葡萄牙',
    regex: /(?:^|[^a-zA-Z])(?:PT|PRT|Portugal|Lisbon)(?:[^a-zA-Z]|$)|葡萄牙|里斯本/i
  },
  // 南非
  {
    code: 'ZA',
    flag: '🇿🇦',
    text: '南非',
    regex: /(?:^|[^a-zA-Z])(?:ZA|ZAF|South\s*Africa|Johannesburg)(?:[^a-zA-Z]|$)|南非|约翰内斯堡/i
  },
  // 阿联酋
  {
    code: 'AE',
    flag: '🇦🇪',
    text: '阿联酋',
    regex: /(?:^|[^a-zA-Z])(?:AE|ARE|UAE|United\s*Arab\s*Emirates|Dubai)(?:[^a-zA-Z]|$)|阿联酋|迪拜/i
  },
  // 中国
  {
    code: 'CN',
    flag: '🇨🇳',
    text: '中国',
    regex: /(?:^|[^a-zA-Z])(?:CN|CHN|China)(?:[^a-zA-Z]|$)|中国|回国|国内|北京|上海|广州|深圳/i
  }
]

// 3. Cloudflare Anycast IP 段前缀
const CF_IP_PREFIXES = [
  '104.16.', '104.17.', '104.18.', '104.19.', '104.20.', '104.21.', '104.22.', '104.23.',
  '104.24.', '104.25.', '104.26.', '104.27.', '104.28.', '104.29.', '104.30.', '104.31.',
  '172.64.', '172.65.', '172.66.', '172.67.', '172.68.', '172.69.', '172.70.', '172.71.',
  '162.158.', '162.159.', '198.41.', '141.101.', '108.162.', '190.93.', '188.114.'
]

export function isCloudflare(name = '', server = '') {
  const s = String(server).trim().toLowerCase()
  const n = String(name).trim().toLowerCase()
  if (n.includes('cloudflare') || n.includes('cf官方') || n.includes('cf优选') || n.startsWith('cf')) {
    return true
  }
  return CF_IP_PREFIXES.some(prefix => s.startsWith(prefix))
}

/**
 * 获取节点的归属国家/区域信息（同步+带异步缓存）
 * @param {Object} node 节点对象 (包含 name, server 等)
 * @param {Object} ipCache IP/域名解析缓存字典
 * @returns {{ code: string, flag: string, text: string, fullText: string }}
 */
export function getNodeLocation(node, ipCache = {}) {
  const fallback = { code: 'UN', flag: '🌐', text: '未知区域', fullText: '未知区域', svg: getFlagSvg('CF') }
  if (!node) {
    return fallback
  }

  const name = String(node.name || '').trim()
  const server = String(node.server || '').trim()

  const makeRes = (code, flag, text, fullText) => ({
    code,
    flag,
    text,
    fullText: fullText || `${flag} ${text}`,
    svg: getFlagSvg(code)
  })

  // 1. 检查国旗 Emoji（节点名最显眼的国家标志）
  for (const [flag, info] of Object.entries(EMOJI_FLAG_MAP)) {
    if (name.includes(flag)) {
      return makeRes(info.code, info.flag, info.text, `${info.flag} ${info.text}`)
    }
  }

  // 2. 检查常见国家规则匹配（优先针对节点名称，中继节点的出口地区由节点名决定，而入口中继IP通常是其他国家的）
  for (const rule of LOCATION_RULES) {
    if (rule.regex.test(name)) {
      return makeRes(rule.code, rule.flag, rule.text, `${rule.flag} ${rule.text}`)
    }
  }

  // 3. 检查 Cloudflare Anycast IP 段或名称
  if (isCloudflare(name, server)) {
    return makeRes('CF', '🌐', 'Cloudflare Anycast', '🌐 Cloudflare Anycast')
  }

  // 4. 节点名称未包含区域信息时，检查异步 IP GeoIP 解析结果
  if (server && ipCache && ipCache[server]) {
    const geo = ipCache[server]
    if (geo && geo.country) {
      const cityPart = geo.city && geo.city !== geo.country ? ` · ${geo.city}` : ''
      const displayText = `${geo.country}${cityPart}`
      const cCode = geo.countryCode || 'IP'
      return makeRes(cCode, geo.flag || '🌐', displayText, `${geo.flag || '🌐'} ${geo.country}${cityPart}`)
    }
  }

  // 5. 检查节点服务器域名中的地域代号 (如 sg07.150239.xyz, hk.node.com)
  if (server) {
    for (const rule of LOCATION_RULES) {
      if (rule.regex.test(server)) {
        return makeRes(rule.code, rule.flag, rule.text, `${rule.flag} ${rule.text}`)
      }
    }
  }

  // 6. 默认未识别标识
  return fallback
}

// 2 位国家大写代码与国家信息对照表
export const CODE_TO_COUNTRY_MAP = {
  HK: { flag: '🇭🇰', text: '香港', code: 'HK' },
  TW: { flag: '🇹🇼', text: '台湾', code: 'TW' },
  JP: { flag: '🇯🇵', text: '日本', code: 'JP' },
  SG: { flag: '🇸🇬', text: '新加坡', code: 'SG' },
  US: { flag: '🇺🇸', text: '美国', code: 'US' },
  KR: { flag: '🇰🇷', text: '韩国', code: 'KR' },
  GB: { flag: '🇬🇧', text: '英国', code: 'GB' },
  UK: { flag: '🇬🇧', text: '英国', code: 'GB' },
  DE: { flag: '🇩🇪', text: '德国', code: 'DE' },
  FR: { flag: '🇫🇷', text: '法国', code: 'FR' },
  CA: { flag: '🇨🇦', text: '加拿大', code: 'CA' },
  AU: { flag: '🇦🇺', text: '澳大利亚', code: 'AU' },
  RU: { flag: '🇷🇺', text: '俄罗斯', code: 'RU' },
  IN: { flag: '🇮🇳', text: '印度', code: 'IN' },
  TH: { flag: '🇹🇭', text: '泰国', code: 'TH' },
  VN: { flag: '🇻🇳', text: '越南', code: 'VN' },
  PH: { flag: '🇵🇭', text: '菲律宾', code: 'PH' },
  MY: { flag: '🇲🇾', text: '马来西亚', code: 'MY' },
  NL: { flag: '🇳🇱', text: '荷兰', code: 'NL' },
  TR: { flag: '🇹🇷', text: '土耳其', code: 'TR' },
  AR: { flag: '🇦🇷', text: '阿根廷', code: 'AR' },
  BR: { flag: '🇧🇷', text: '巴西', code: 'BR' },
  MX: { flag: '🇲🇽', text: '墨西哥', code: 'MX' },
  ID: { flag: '🇮🇩', text: '印尼', code: 'ID' },
  CH: { flag: '🇨🇭', text: '瑞士', code: 'CH' },
  SE: { flag: '🇸🇪', text: '瑞典', code: 'SE' },
  NO: { flag: '🇳🇴', text: '挪威', code: 'NO' },
  FI: { flag: '🇫🇮', text: '芬兰', code: 'FI' },
  IE: { flag: '🇮🇪', text: '爱尔兰', code: 'IE' },
  IT: { flag: '🇮🇹', text: '意大利', code: 'IT' },
  ES: { flag: '🇪🇸', text: '西班牙', code: 'ES' },
  PT: { flag: '🇵🇹', text: '葡萄牙', code: 'PT' },
  ZA: { flag: '🇿🇦', text: '南非', code: 'ZA' },
  AE: { flag: '🇦🇪', text: '阿联酋', code: 'AE' },
  CN: { flag: '🇨🇳', text: '中国', code: 'CN' },
  MO: { flag: '🇲🇴', text: '澳门', code: 'MO' }
}

/**
 * 若带有 2 位国家大写代码前缀 (如 "HK 003", "TW 01", "US-01", "SG_01", "HK01")，
 * 把大写代码汉化，前面再加上国家代码 Emoji (如 "HK 003" -> "🇭🇰 香港 003")
 * @param {string} origName 
 * @returns {string|null}
 */
export function convertCodePrefix(origName) {
  if (!origName) return null
  const codes = Object.keys(CODE_TO_COUNTRY_MAP).join('|')
  const codeRegex = new RegExp(`^(${codes})(?:([\\s\\-_]+)|(?=[0-9]))(.*)$`, 'i')
  const match = origName.match(codeRegex)
  if (!match) return null

  const upperCode = match[1].toUpperCase()
  const info = CODE_TO_COUNTRY_MAP[upperCode]
  if (!info) return null

  const sep = match[2] || ' '
  const rest = (match[3] || '').trim()

  // 如果后续内容本身已经带有该国家中文名或中国，避免重复 (如 'HK 香港01', 'HK 中国 香港')
  if (rest.startsWith(info.text) || (info.code === 'HK' && rest.startsWith('中国')) || (info.code === 'TW' && rest.startsWith('中国'))) {
    return `${info.flag} ${rest}`
  }

  return `${info.flag} ${info.text}${sep}${rest}`
}

/**
 * 检查节点名称前面是否已有国旗代码或国家前缀
 * @param {string} name 节点名称
 * @returns {boolean}
 */
export function hasFlagOrCodePrefix(name) {
  if (!name) return false
  const trimmed = String(name).trim()

  // 1. 是否以 Unicode 国旗 Emoji (Regional Indicator 序列，例如 🇭🇰, 🇦🇺, 🇺🇸, 🇺🇲 等) 开头
  if (/^[\u{1F1E6}-\u{1F1FF}]{2}/u.test(trimmed)) {
    return true
  }

  // 2. 是否以 EMOJI_FLAG_MAP 中的任意国旗符号开头
  for (const flag of Object.keys(EMOJI_FLAG_MAP)) {
    if (trimmed.startsWith(flag)) {
      return true
    }
  }

  // 3. 是否以 2 位国家大写代码 + (空格/短横线/下划线/数字) 开头，如 "HK 003", "TW 01", "US-01", "SG_01", "HK01"
  const countryCodes = Array.from(new Set(Object.values(EMOJI_FLAG_MAP).map(v => v.code).concat(['UK', 'MO'])))
  const codeRegex = new RegExp(`^(${countryCodes.join('|')})(?:[\\s\\-_]|(?=[0-9]))`, 'i')
  if (codeRegex.test(trimmed)) {
    return true
  }

  return false
}

/**
 * 当节点名称前面没有国旗代码时，自动补全国旗代码+空格；
 * 若已带有 2 位国家大写代码前缀，把大写代码汉化，前面再加上国家代码
 * @param {string} name 节点名称
 * @param {Object} node 节点对象 (包含 name, server 等)
 * @param {Object} ipCache IP/域名解析缓存字典
 * @returns {string} 补全/规范化后的节点名称
 */
export function formatNodeNameWithFlag(name, node = {}, ipCache = {}) {
  const origName = String(name || node?.name || '').trim()
  if (!origName) return origName

  // 1. 如果已经包含国旗 Emoji，但紧跟文字没有空格 (如 "🇭🇰香港01")，规范化补上空格
  const emojiMatch = origName.match(/^([\u{1F1E6}-\u{1F1FF}]{2})(\S.*)$/u)
  if (emojiMatch) {
    return `${emojiMatch[1]} ${emojiMatch[2]}`
  }

  // 2. 如果已经包含国旗 Emoji 前缀 (如 "🇭🇰 中国 香港-BGP", "🇭🇰 香港01")，不重复添加
  if (/^[\u{1F1E6}-\u{1F1FF}]{2}/u.test(origName)) {
    return origName
  }
  for (const flag of Object.keys(EMOJI_FLAG_MAP)) {
    if (origName.startsWith(flag)) {
      return origName
    }
  }

  // 3. 若带有 2 位国家大写代码前缀 (如 "HK 003", "TW 01", "US-01", "SG_01", "HK01")：
  //    把大写代码汉化，前面再加上国家代码 Emoji (如 "HK 003" -> "🇭🇰 香港 003")
  const converted = convertCodePrefix(origName)
  if (converted) {
    return converted
  }

  // 4. 解析节点的归属地信息 (针对未带国家代码但含有中文地名/中继名称的节点，如 "香港CF3", "美国CF2", "日本623 中继")
  const loc = getNodeLocation({ ...node, name: origName }, ipCache)

  // 5. 若成功识别出具体国家/地区且有国旗 Emoji，自动补全国旗 Emoji + 空格
  if (loc && loc.code !== 'UN' && loc.code !== 'CF' && loc.flag && loc.flag !== '🌐') {
    return `${loc.flag} ${origName}`
  }

  return origName
}

/**
 * 提取不变的节点信息元素生成唯一特征标识（协议 + 服务器地址 + 端口 + 凭证）
 * 用于跨重命名、国旗补全、格式化等场景精准判断节点是否已导入/已存在
 * @param {Object} node 节点对象或 raw 代理对象
 * @returns {string} 节点的不变唯一特征标识
 */
export function getNodeIdentityKey(node) {
  if (!node || typeof node !== 'object') return ''
  const raw = (node.raw && typeof node.raw === 'object') ? node.raw : node
  const ptype = String(raw.type || node.type || '').trim().toLowerCase()
  let server = String(raw.server || node.server || '').trim().toLowerCase()
  if (server.startsWith('[') && server.endsWith(']')) {
    server = server.slice(1, -1)
  }
  const port = String(raw.ports || node.ports || raw.port || node.port || '').trim()
  if (!server || !port) return ''

  const cred = String(
    raw.uuid || node.uuid ||
    raw.password || node.password ||
    raw.auth_str || node.auth_str ||
    raw.auth || node.auth ||
    raw['public-key'] || node['public-key'] ||
    ''
  ).trim().toLowerCase()

  if (cred) {
    return `${ptype}://${server}:${port}@${cred}`
  }
  return `${ptype}://${server}:${port}`
}


