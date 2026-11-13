local in_question = false
local in_answer = false
local in_analysis = false

local function raw(s)
  return pandoc.RawBlock("latex", s)
end

local function stringify_block(block)
  if block.content then
    return pandoc.utils.stringify(block.content)
  end
  return pandoc.utils.stringify(block)
end

local function close_question(out)
  if in_question then
    table.insert(out, raw("\\end{questionbox}"))
    in_question = false
  end
end

local function close_answer(out)
  if in_answer then
    table.insert(out, raw("\\end{answerbox}"))
    in_answer = false
  end
end

local function close_analysis(out)
  if in_analysis then
    table.insert(out, raw("\\end{analysisbox}"))
    in_analysis = false
  end
end

local function close_all(out)
  close_analysis(out)
  close_answer(out)
  close_question(out)
end

local function starts_question(block)
  if block.t ~= "Para" then
    return false
  end
  local text = stringify_block(block)
  return text:match("^%s*%d+%.") ~= nil
end

local function starts_answer(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  local text = stringify_block(block)
  return text:match("^%s*答案[：:]") ~= nil
end

local function starts_analysis(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  local text = stringify_block(block)
  return text:match("^%s*解析[：:]") ~= nil
end

local function has_image(inlines)
  for _, inline in ipairs(inlines) do
    if inline.t == "Image" then
      return true
    end
  end
  return false
end

local function is_image_block(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return false
  end
  return has_image(block.content)
end

function Pandoc(doc)
  local out = {}

  for i, block in ipairs(doc.blocks) do
    local next_block = doc.blocks[i + 1]
    if block.t == "Header" then
      if block.level <= 2 then
        close_all(out)
      end
      table.insert(out, block)
    elseif block.t == "HorizontalRule" then
      close_all(out)
    elseif starts_analysis(block) then
      close_question(out)
      close_answer(out)
      if not in_analysis then
        table.insert(out, raw("\\begin{analysisbox}"))
        in_analysis = true
      end
      table.insert(out, block)
    elseif starts_answer(block) then
      close_question(out)
      close_analysis(out)
      if not in_answer then
        table.insert(out, raw("\\begin{answerbox}"))
        in_answer = true
      end
      table.insert(out, block)
    elseif is_image_block(block) then
      if not in_question and next_block and (next_block.t == "HorizontalRule" or starts_question(next_block)) then
        close_analysis(out)
        close_answer(out)
      end
      table.insert(out, block)
    elseif starts_question(block) then
      close_all(out)
      table.insert(out, raw("\\begin{questionbox}"))
      in_question = true
      table.insert(out, block)
    else
      table.insert(out, block)
    end
  end

  close_all(out)
  return pandoc.Pandoc(out, doc.meta)
end
