local function raw(text)
  return pandoc.RawBlock("latex", text)
end

local function has_class(el, class_name)
  for _, value in ipairs(el.classes or {}) do
    if value == class_name then
      return true
    end
  end
  return false
end

function Div(el)
  local begin_env = nil
  local end_env = nil

  if has_class(el, "kami-teacher-answer") then
    begin_env = "\\begin{kamiteacheranswerbox}"
    end_env = "\\end{kamiteacheranswerbox}"
  elseif has_class(el, "kami-teacher-solution") then
    begin_env = "\\begin{kamiteachersolutionbox}"
    end_env = "\\end{kamiteachersolutionbox}"
  elseif has_class(el, "kami-teacher-note") then
    local title = el.attributes["data-title"] or "重点"
    begin_env = "\\begin{kamiteachernotebox}[" .. title .. "]"
    end_env = "\\end{kamiteachernotebox}"
  elseif has_class(el, "kami-teacher-summary") then
    begin_env = "\\begin{kamiteachersummarybox}"
    end_env = "\\end{kamiteachersummarybox}"
  end

  if not begin_env then
    return nil
  end

  local blocks = {raw(begin_env)}
  for _, block in ipairs(el.content) do
    table.insert(blocks, block)
  end
  table.insert(blocks, raw(end_env))
  return blocks
end

local function image_only(block)
  if block.t ~= "Para" and block.t ~= "Plain" then
    return nil
  end
  if #block.content ~= 1 or block.content[1].t ~= "Image" then
    return nil
  end
  return block.content[1]
end

function Para(el)
  local image = image_only(el)
  if not image then
    return nil
  end
  image.caption = {}
  if not image.attributes["width"] then
    image.attributes["width"] = "58%"
  end
  if not image.attributes["height"] then
    image.attributes["height"] = "27%"
  end
  return {raw("\\begin{center}"), el, raw("\\end{center}")}
end
